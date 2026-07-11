import logging
import platform
import subprocess
import time

import psutil  # type: ignore[import-untyped]

from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.providers.base import Provider

logger = logging.getLogger(__name__)


class PsutilProvider(Provider):
    def __init__(self) -> None:
        self._start_time = time.time()
        self._last_time: float = 0.0
        self._last_disk_io: dict[
            str, tuple[int, int]
        ] = {}  # device -> (read_bytes, write_bytes)
        self._last_net_io: dict[
            str, tuple[int, int]
        ] = {}  # interface -> (bytes_sent, bytes_recv)
        self._processes: dict[int, psutil.Process] = {}  # pid -> Process object

        # Load static specs once
        self._cpu_model = self._get_cpu_model()
        self._os_version = self._get_os_version()
        try:
            self._total_memory = psutil.virtual_memory().total
        except Exception:
            self._total_memory = 0

    @property
    def name(self) -> str:
        return "psutil"

    def available(self) -> bool:
        return True

    def read(self) -> list[MetricReading]:
        readings: list[MetricReading] = []
        now = time.time()

        # Elapsed calculation (ensure we don't divide by zero)
        elapsed = now - self._last_time if self._last_time > 0 else 0.0

        # 1. CPU metrics
        try:
            # overall CPU utilization
            cpu_total = psutil.cpu_percent(interval=None)
            readings.append(
                MetricReading(
                    metric="cpu.utilization.total",
                    value=cpu_total,
                    unit=MetricUnit.PERCENT,
                    source=self.name,
                )
            )

            # per-core CPU utilization
            cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
            for idx, val in enumerate(cpu_cores):
                readings.append(
                    MetricReading(
                        metric="cpu.utilization.per_core",
                        value=val,
                        unit=MetricUnit.PERCENT,
                        source=self.name,
                        tags={"core": str(idx)},
                    )
                )

            # cpu frequency
            cpu_freq = psutil.cpu_freq()
            if cpu_freq and cpu_freq.current:
                # current is in MHz, convert to HERTZ
                readings.append(
                    MetricReading(
                        metric="cpu.frequency.current",
                        value=cpu_freq.current * 1_000_000.0,
                        unit=MetricUnit.HERTZ,
                        source=self.name,
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to read CPU metrics from psutil: {e}")

        # 2. Memory metrics
        try:
            vm = psutil.virtual_memory()
            readings.append(
                MetricReading(
                    metric="memory.used",
                    value=float(vm.used),
                    unit=MetricUnit.BYTES,
                    source=self.name,
                )
            )
            readings.append(
                MetricReading(
                    metric="memory.available",
                    value=float(vm.available),
                    unit=MetricUnit.BYTES,
                    source=self.name,
                )
            )
            readings.append(
                MetricReading(
                    metric="memory.utilization",
                    value=vm.percent,
                    unit=MetricUnit.PERCENT,
                    source=self.name,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to read memory metrics from psutil: {e}")

        # 3. Disk partition usage
        try:
            partitions = psutil.disk_partitions(all=False)
            for part in partitions:
                # Skip mountpoints that are pseudo or read-only/unreadable to avoid hang
                if not part.mountpoint or "cdrom" in part.opts:
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    readings.append(
                        MetricReading(
                            metric="disk.usage.used",
                            value=float(usage.used),
                            unit=MetricUnit.BYTES,
                            source=self.name,
                            tags={"device": part.device, "mountpoint": part.mountpoint},
                        )
                    )
                except PermissionError:
                    # Occurs on macOS containers/system partitions
                    continue
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Failed to read disk partition metrics from psutil: {e}")

        # 4. Disk I/O throughput (computed as rate)
        try:
            disk_io = psutil.disk_io_counters(perdisk=True)
            if disk_io:
                for disk_name, io in disk_io.items():
                    if elapsed > 0.0 and disk_name in self._last_disk_io:
                        prev_read, prev_write = self._last_disk_io[disk_name]
                        read_rate = (io.read_bytes - prev_read) / elapsed
                        write_rate = (io.write_bytes - prev_write) / elapsed

                        if read_rate >= 0:
                            readings.append(
                                MetricReading(
                                    metric="disk.io.read_bytes",
                                    value=read_rate,
                                    unit=MetricUnit.BYTES_PER_SEC,
                                    source=self.name,
                                    tags={"device": disk_name},
                                )
                            )
                        if write_rate >= 0:
                            readings.append(
                                MetricReading(
                                    metric="disk.io.write_bytes",
                                    value=write_rate,
                                    unit=MetricUnit.BYTES_PER_SEC,
                                    source=self.name,
                                    tags={"device": disk_name},
                                )
                            )
                    self._last_disk_io[disk_name] = (io.read_bytes, io.write_bytes)
        except Exception as e:
            logger.warning(f"Failed to read disk I/O metrics from psutil: {e}")

        # 5. Network I/O throughput (computed as rate)
        try:
            net_io = psutil.net_io_counters(pernic=True)
            if net_io:
                for interface, io in net_io.items():
                    # Ignore loopback interfaces to keep metrics relevant
                    if (
                        interface.startswith("lo")
                        or interface == "gif0"
                        or interface == "stf0"
                    ):
                        continue
                    if elapsed > 0.0 and interface in self._last_net_io:
                        prev_sent, prev_recv = self._last_net_io[interface]
                        sent_rate = (io.bytes_sent - prev_sent) / elapsed
                        recv_rate = (io.bytes_recv - prev_recv) / elapsed

                        if sent_rate >= 0:
                            readings.append(
                                MetricReading(
                                    metric="network.io.bytes_sent",
                                    value=sent_rate,
                                    unit=MetricUnit.BYTES_PER_SEC,
                                    source=self.name,
                                    tags={"interface": interface},
                                )
                            )
                        if recv_rate >= 0:
                            readings.append(
                                MetricReading(
                                    metric="network.io.bytes_recv",
                                    value=recv_rate,
                                    unit=MetricUnit.BYTES_PER_SEC,
                                    source=self.name,
                                    tags={"interface": interface},
                                )
                            )
                    self._last_net_io[interface] = (io.bytes_sent, io.bytes_recv)
        except Exception as e:
            logger.warning(f"Failed to read net I/O metrics from psutil: {e}")

        # 6. Per-process resource utilization (Top 5 by CPU)
        try:
            current_pids = set()
            proc_list = []

            # Retrieve currently running processes
            for p in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    pid = p.info["pid"]
                    name = p.info["name"] or "unknown"
                    current_pids.add(pid)

                    # Keep track of Process object for accurate cpu_percent over ticks
                    if pid not in self._processes:
                        self._processes[pid] = p

                    proc = self._processes[pid]
                    # Non-blocking cpu percent check
                    cpu_pct = proc.cpu_percent(interval=None)

                    # Memory usage
                    mem_info = proc.memory_info()
                    rss = float(mem_info.rss)

                    proc_list.append((cpu_pct, rss, pid, name))
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue

            # Cleanup self._processes for dead processes
            dead_pids = set(self._processes.keys()) - current_pids
            for dp in dead_pids:
                self._processes.pop(dp, None)

            # Sort by CPU utilization descending and take top 5
            proc_list.sort(key=lambda x: x[0], reverse=True)
            top_5 = proc_list[:5]

            for cpu_pct, rss, pid, name in top_5:
                # CPU metric
                readings.append(
                    MetricReading(
                        metric="process.cpu_percent",
                        value=cpu_pct,
                        unit=MetricUnit.PERCENT,
                        source=self.name,
                        tags={"pid": str(pid), "name": name},
                    )
                )
                # Memory metric
                readings.append(
                    MetricReading(
                        metric="process.memory.used",
                        value=rss,
                        unit=MetricUnit.BYTES,
                        source=self.name,
                        tags={"pid": str(pid), "name": name},
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to read process utilization from psutil: {e}")

        # 7. Static system info specs
        readings.append(
            MetricReading(
                metric="system.info.cpu_model",
                value=0.0,
                unit=MetricUnit.INFO,
                source=self.name,
                tags={"value": self._cpu_model},
            )
        )
        readings.append(
            MetricReading(
                metric="system.info.os_version",
                value=0.0,
                unit=MetricUnit.INFO,
                source=self.name,
                tags={"value": self._os_version},
            )
        )
        readings.append(
            MetricReading(
                metric="system.info.total_memory",
                value=0.0,
                unit=MetricUnit.INFO,
                source=self.name,
                tags={"value": str(self._total_memory)},
            )
        )

        self._last_time = now
        return readings

    def _get_cpu_model(self) -> str:
        """Helper to retrieve processor brand info across systems."""
        try:
            if platform.system() == "Darwin":
                # macOS specific sysctl brand info
                brand = (
                    subprocess.check_output(
                        ["sysctl", "-n", "machdep.cpu.brand_string"]
                    )
                    .decode()
                    .strip()
                )
                if brand:
                    return brand

                # fallback for some Apple Silicon models
                model = (
                    subprocess.check_output(["sysctl", "-n", "hw.model"])
                    .decode()
                    .strip()
                )
                return model if model else "Apple Silicon"
            elif platform.system() == "Windows":
                # Windows registry brand info
                import typing
                import winreg

                winreg_any: typing.Any = winreg
                key = winreg_any.OpenKey(
                    winreg_any.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                )
                processor_name, _ = winreg_any.QueryValueEx(key, "ProcessorNameString")
                return str(processor_name).strip()
            elif platform.system() == "Linux":
                # Linux cat cpuinfo info
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
        except Exception:
            pass
        return platform.processor() or platform.machine() or "Unknown CPU"

    def _get_os_version(self) -> str:
        """Helper to construct platform OS and release version."""
        try:
            return f"{platform.system()} {platform.release()} ({platform.version()})"
        except Exception:
            return platform.system() or "Unknown OS"
