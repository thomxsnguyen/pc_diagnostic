import logging
import time
from typing import Any

from rich.box import ROUNDED
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress
from rich.table import Table
from rich.text import Text

from pc_diagnostic.alerts.dispatcher import AlertDispatcher
from pc_diagnostic.cache import RollingCache
from pc_diagnostic.models import MetricReading

logger = logging.getLogger(__name__)


def format_bytes(bytes_val: float) -> str:
    """Format bytes values into human readable suffixes."""
    if bytes_val < 1024:
        return f"{bytes_val:.1f} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"


def format_rate(bytes_per_sec: float) -> str:
    """Format throughput rate values into human readable suffixes."""
    return f"{format_bytes(bytes_per_sec)}/s"


def get_bar_style(percent: float) -> str:
    """Select appropriate styling based on percentage thresholds."""
    if percent > 80.0:
        return "bold red"
    elif percent > 50.0:
        return "bold yellow"
    else:
        return "bold green"


class TerminalDashboard:
    def __init__(
        self, cache: RollingCache, dispatcher: AlertDispatcher | None = None
    ) -> None:
        self.cache = cache
        self.dispatcher = dispatcher
        self.console = Console()

    def _get_metric_val(
        self, metrics: dict[str, list[MetricReading]], name: str, default: float = 0.0
    ) -> float:
        """Safely retrieve metric value with default fallback."""
        if metrics.get(name):
            return metrics[name][0].value
        return default

    def _get_metric_tag(
        self,
        metrics: dict[str, list[MetricReading]],
        name: str,
        tag_key: str,
        default: str = "",
    ) -> str:
        """Safely retrieve metric tag string with default fallback."""
        if name in metrics and metrics[name] and metrics[name][0].tags:
            return metrics[name][0].tags.get(tag_key, default)
        return default

    def generate_sparkline(
        self, metric: str, max_val: float = 100.0, n: int = 25
    ) -> str:
        """Generate text-based Unicode sparklines representing load history."""
        history = self.cache.series(metric, n)
        if not history:
            return " " * n

        blocks = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        sparkline_chars = []
        for val in history:
            # Clamp percentage value between 0.0 and 1.0
            pct = max(0.0, min(1.0, val / max_val))
            idx = int(pct * (len(blocks) - 1))
            sparkline_chars.append(blocks[idx])
        return "".join(sparkline_chars)

    def generate_layout(self) -> Layout:
        # Initialize layout structure
        layout = Layout()
        layout.split_column(Layout(name="header", size=4), Layout(name="body"))
        layout["body"].split_row(
            Layout(name="left", ratio=1), Layout(name="right", ratio=1)
        )
        layout["left"].split_column(
            Layout(name="cpu", ratio=4),
            Layout(name="memory", ratio=2),
            Layout(name="io", ratio=3),
        )
        layout["right"].split_column(
            Layout(name="processes", ratio=4),
            Layout(name="thermals", ratio=2),
            Layout(name="alerts", ratio=2),
            Layout(name="specs", ratio=2),
        )
        return layout

    def render(self, layout: Layout) -> None:
        latest = self.cache.latest()
        health = self.cache.health()

        # If cache is completely empty, render simple loading state
        if not latest:
            loading_panel = Panel(
                Text(
                    "\nConnecting to PC Diagnostic Collector...\n"
                    "Waiting for first metrics snapshot...",
                    justify="center",
                    style="bold yellow",
                ),
                title="PC Diagnostic v0.1.0",
                box=ROUNDED,
            )
            layout["header"].update(loading_panel)
            layout["body"].update(
                Panel(
                    Text(
                        "No snapshots collected yet. "
                        "Ensure collector background thread is active.",
                        justify="center",
                        style="dim",
                    )
                )
            )
            return

        # Organize readings by metric name
        metrics: dict[str, list[MetricReading]] = {}
        for r in latest.readings:
            metrics.setdefault(r.metric, []).append(r)

        # Alarm logic: Check for stale cache
        is_stale = health.age_s > 2.0

        # 1. RENDER HEADER
        last_update_str = time.strftime("%H:%M:%S", time.localtime(latest.timestamp))
        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left")
        header_table.add_column(justify="center")
        header_table.add_column(justify="right")

        # CPU model & OS specs for header (retrieve from static specs)
        cpu_model = self._get_metric_tag(
            metrics, "system.info.cpu_model", "value", "N/A"
        )
        os_version = self._get_metric_tag(
            metrics, "system.info.os_version", "value", "N/A"
        )

        if is_stale:
            title_text = Text(
                f"[COLLECTOR OFFLINE - DATA STALE ({health.age_s:.1f}s ago)]",
                style="blink bold white on red",
            )
            header_border_style = "bold red"
        else:
            title_text = Text(
                "PC DIAGNOSTIC LIVE TUI MONITOR",
                style="bold white on blue",
            )
            header_border_style = "blue"

        header_table.add_row(
            Text(f" OS: {os_version}", style="bold cyan"),
            title_text,
            Text(
                f"Last Tick: {last_update_str} | "
                f"Cache: {health.size}/{health.max_size} ",
                style="bold red" if is_stale else "bold green",
            ),
        )
        layout["header"].update(
            Panel(header_table, box=ROUNDED, style=header_border_style)
        )

        # 2. RENDER CPU PANEL
        cpu_pct = self._get_metric_val(metrics, "cpu.utilization.total", 0.0)
        cpu_style = get_bar_style(cpu_pct)

        # CPU overall progress bar
        cpu_desc = Text(f"Overall CPU Utilization: {cpu_pct:.1f}%", style="bold")
        cpu_progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(bar_width=35, complete_style=cpu_style, finished_style=cpu_style),
            transient=True,
        )
        cpu_progress.add_task(str(cpu_desc), total=100.0, completed=int(cpu_pct))

        # Per-core CPU utilization
        cores_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        cores_table.add_column(ratio=2)
        cores_table.add_column(ratio=3)
        cores_table.add_column(ratio=2)
        cores_table.add_column(ratio=3)

        per_core_readings = metrics.get("cpu.utilization.per_core", [])

        if per_core_readings:
            # Sort cores numerically by tags["core"]
            per_core_readings.sort(key=lambda r: int(r.tags.get("core", 0)))

            # Build core bars in two columns
            half = (len(per_core_readings) + 1) // 2
            for i in range(half):
                # Col 1
                r1 = per_core_readings[i]
                core_id1 = r1.tags.get("core", "0")
                c_pct1 = r1.value
                c_style1 = get_bar_style(c_pct1)
                prog1 = Progress(
                    BarColumn(
                        bar_width=12, complete_style=c_style1, finished_style=c_style1
                    )
                )
                prog1.add_task("", total=100.0, completed=int(c_pct1))

                # Col 2
                if i + half < len(per_core_readings):
                    r2 = per_core_readings[i + half]
                    core_id2 = r2.tags.get("core", "0")
                    c_pct2 = r2.value
                    c_style2 = get_bar_style(c_pct2)
                    prog2 = Progress(
                        BarColumn(
                            bar_width=12,
                            complete_style=c_style2,
                            finished_style=c_style2,
                        )
                    )
                    prog2.add_task("", total=100.0, completed=int(c_pct2))

                    cores_table.add_row(
                        f"Core {core_id1}: {c_pct1:4.1f}%",
                        prog1,
                        f"Core {core_id2}: {c_pct2:4.1f}%",
                        prog2,
                    )
                else:
                    cores_table.add_row(
                        f"Core {core_id1}: {c_pct1:4.1f}%", prog1, "", ""
                    )
        else:
            cores_table.add_row(
                "[dim]N/A (No per-core details found)[/dim]", "", "", ""
            )

        cpu_freq_str = "Unknown Freq"
        if "cpu.frequency.current" in metrics:
            freq_hz = metrics["cpu.frequency.current"][0].value
            cpu_freq_str = f"{freq_hz / 1_000_000.0:.0f} MHz"

        # Generate sparkline history
        cpu_spark = self.generate_sparkline(
            "cpu.utilization.total", max_val=100.0, n=20
        )

        cpu_content = Table.grid(expand=True)
        cpu_content.add_row(cpu_progress.get_renderable())
        cpu_content.add_row(
            Text.assemble(
                Text(f"CPU Model: {cpu_model} ({cpu_freq_str})", style="dim"),
                Text(" " * 4),
                Text("Trend: ", style="bold cyan"),
                Text(cpu_spark, style="cyan"),
            )
        )
        cpu_content.add_row(Text("-" * 50, style="dim"))
        cpu_content.add_row(cores_table)
        layout["cpu"].update(
            Panel(
                cpu_content, title="[bold cyan]CPU Utilization[/bold cyan]", box=ROUNDED
            )
        )

        # 3. RENDER MEMORY PANEL
        mem_pct = self._get_metric_val(metrics, "memory.utilization", 0.0)
        mem_used = self._get_metric_val(metrics, "memory.used", 0.0)
        mem_avail = self._get_metric_val(metrics, "memory.available", 0.0)
        mem_total = self._get_metric_val(metrics, "memory.total", 0.0)
        if mem_total == 0.0:
            mem_total = mem_used + mem_avail

        mem_used_str = format_bytes(mem_used)
        mem_total_str = format_bytes(mem_total)
        mem_desc = Text(
            f"RAM Utilization: {mem_pct:.1f}% ({mem_used_str} / {mem_total_str})",
            style="bold",
        )
        mem_style = get_bar_style(mem_pct)
        mem_progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(bar_width=35, complete_style=mem_style, finished_style=mem_style),
            transient=True,
        )
        mem_progress.add_task(str(mem_desc), total=100.0, completed=int(mem_pct))

        # Generate Memory sparkline history
        mem_spark = self.generate_sparkline("memory.utilization", max_val=100.0, n=20)

        mem_content = Table.grid(expand=True)
        mem_content.add_row(mem_progress.get_renderable())
        mem_content.add_row(
            Text.assemble(
                Text(f"Available RAM: {format_bytes(mem_avail)}", style="dim"),
                Text(" " * 6),
                Text("Trend: ", style="bold green"),
                Text(mem_spark, style="green"),
            )
        )
        layout["memory"].update(
            Panel(mem_content, title="[bold green]Memory[/bold green]", box=ROUNDED)
        )

        # 4. RENDER I/O (STORAGE & NETWORK)
        io_table = Table.grid(expand=True)
        io_table.add_column(ratio=1)
        io_table.add_column(ratio=1)

        # Storage sub-section
        storage_info = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        storage_info.add_column()
        storage_info.add_column()
        storage_info.add_row(Text("Storage Usage", style="bold yellow"), "")

        disk_used_metrics = metrics.get("disk.usage.used", [])
        if disk_used_metrics:
            for dm in disk_used_metrics:
                device = dm.tags.get("device", "Disk")
                mount = dm.tags.get("mountpoint", "/")
                used_bytes = dm.value
                storage_info.add_row(
                    Text(f"  Disk {mount} ({device}):"),
                    Text(f"{format_bytes(used_bytes)} used", style="yellow"),
                )
        else:
            storage_info.add_row(Text("  No storage data [N/A]", style="dim"), "")

        # Disk I/O throughput rate
        read_rate = 0.0
        write_rate = 0.0
        if "disk.io.read_bytes" in metrics:
            read_rate = sum(r.value for r in metrics["disk.io.read_bytes"])
        if "disk.io.write_bytes" in metrics:
            write_rate = sum(r.value for r in metrics["disk.io.write_bytes"])

        storage_info.add_row(
            Text("  Read Rate:"), Text(format_rate(read_rate), style="bold green")
        )
        storage_info.add_row(
            Text("  Write Rate:"), Text(format_rate(write_rate), style="bold yellow")
        )

        # Network throughput rate
        net_sent = 0.0
        net_recv = 0.0
        if "network.io.bytes_sent" in metrics:
            net_sent = sum(r.value for r in metrics["network.io.bytes_sent"])
        if "network.io.bytes_recv" in metrics:
            net_recv = sum(r.value for r in metrics["network.io.bytes_recv"])

        network_info = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        network_info.add_column()
        network_info.add_column()
        network_info.add_row(Text("Network I/O", style="bold magenta"), "")

        net_sent_metrics = metrics.get("network.io.bytes_sent", [])
        net_recv_metrics = metrics.get("network.io.bytes_recv", [])
        if not net_sent_metrics and not net_recv_metrics:
            network_info.add_row(Text("  Upload: [N/A]", style="dim"), "")
            network_info.add_row(Text("  Download: [N/A]", style="dim"), "")
        else:
            network_info.add_row(
                Text("  Upload (Tx):"),
                Text(format_rate(net_sent), style="bold magenta"),
            )
            network_info.add_row(
                Text("  Download (Rx):"), Text(format_rate(net_recv), style="bold cyan")
            )

        io_table.add_row(storage_info, network_info)
        layout["io"].update(
            Panel(
                io_table,
                title="[bold orange3]I/O Throughput & Storage[/bold orange3]",
                box=ROUNDED,
            )
        )

        # 5. RENDER TOP PROCESSES
        proc_cpus = metrics.get("process.cpu_percent", [])
        proc_mems = metrics.get("process.memory.used", [])

        # Build CPU top processes map & Memory top processes map
        cpu_proc_map: dict[str, dict[str, Any]] = {}
        mem_proc_map: dict[str, dict[str, Any]] = {}

        has_type_tags = any("type" in r.tags for r in proc_cpus)

        if has_type_tags:
            # Map elements matching specific category types
            for r in proc_cpus:
                pid = r.tags.get("pid", "0")
                name = r.tags.get("name", "unknown")
                ptype = r.tags.get("type", "cpu_top")
                if ptype == "cpu_top":
                    cpu_proc_map[pid] = {
                        "pid": pid,
                        "name": name,
                        "cpu": r.value,
                        "mem": 0.0,
                    }
                elif ptype == "mem_top":
                    mem_proc_map[pid] = {
                        "pid": pid,
                        "name": name,
                        "cpu": r.value,
                        "mem": 0.0,
                    }
            for r in proc_mems:
                pid = r.tags.get("pid", "0")
                ptype = r.tags.get("type", "cpu_top")
                if ptype == "cpu_top" and pid in cpu_proc_map:
                    cpu_proc_map[pid]["mem"] = r.value
                elif ptype == "mem_top" and pid in mem_proc_map:
                    mem_proc_map[pid]["mem"] = r.value
        else:
            # Fallback for mock readings / older schemas
            for r in proc_cpus:
                pid = r.tags.get("pid", "0")
                name = r.tags.get("name", "unknown")
                cpu_proc_map[pid] = {
                    "pid": pid,
                    "name": name,
                    "cpu": r.value,
                    "mem": 0.0,
                }
            for r in proc_mems:
                pid = r.tags.get("pid", "0")
                if pid in cpu_proc_map:
                    cpu_proc_map[pid]["mem"] = r.value

        # Render Left Table: Top CPU
        cpu_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        cpu_table.add_column(justify="right")
        cpu_table.add_column(style="bold")
        cpu_table.add_column(justify="right")
        cpu_table.add_column(justify="right")

        cpu_table.add_row(Text("Top CPU Processes", style="bold red"), "", "", "")
        cpu_table.add_row(
            Text("PID", style="dim"),
            Text("Name", style="dim"),
            Text("CPU %", style="dim"),
            Text("RAM", style="dim"),
        )

        sorted_cpu_procs = sorted(
            cpu_proc_map.values(), key=lambda x: x["cpu"], reverse=True
        )
        for p in sorted_cpu_procs:
            c_style = (
                "red" if p["cpu"] > 30.0 else ("yellow" if p["cpu"] > 10.0 else "green")
            )
            cpu_table.add_row(
                p["pid"],
                p["name"],
                Text(f"{p['cpu']:.1f}%", style=c_style),
                format_bytes(p["mem"]),
            )

        # Render Right Table: Top Memory
        mem_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        mem_table.add_column(justify="right")
        mem_table.add_column(style="bold")
        mem_table.add_column(justify="right")
        mem_table.add_column(justify="right")

        mem_table.add_row(
            Text("Top Memory Processes", style="bold orange3"), "", "", ""
        )
        mem_table.add_row(
            Text("PID", style="dim"),
            Text("Name", style="dim"),
            Text("CPU %", style="dim"),
            Text("RAM", style="dim"),
        )

        sorted_mem_procs = sorted(
            mem_proc_map.values(), key=lambda x: x["mem"], reverse=True
        )
        for p in sorted_mem_procs:
            c_style = (
                "red" if p["cpu"] > 30.0 else ("yellow" if p["cpu"] > 10.0 else "green")
            )
            mem_table.add_row(
                p["pid"],
                p["name"],
                Text(f"{p['cpu']:.1f}%", style=c_style),
                format_bytes(p["mem"]),
            )

        # Arrange side-by-side inside grid
        proc_grid = Table(box=None, padding=(0, 2), show_header=False, expand=True)
        proc_grid.add_column(ratio=1)
        proc_grid.add_column(ratio=1)
        proc_grid.add_row(cpu_table, mem_table)

        layout["processes"].update(
            Panel(
                proc_grid,
                title="[bold red]Resource Process Monitor[/bold red]",
                box=ROUNDED,
            )
        )

        # 6. RENDER THERMALS & FANS PANEL
        cpu_temp = self._get_metric_val(metrics, "system.temperature.cpu", -1.0)
        gpu_temp = self._get_metric_val(metrics, "system.temperature.gpu", -1.0)
        fan_speed = self._get_metric_val(metrics, "system.fan.speed", -1.0)
        cpu_volt = self._get_metric_val(metrics, "system.voltage.cpu", -1.0)

        thermal_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        thermal_table.add_column()
        thermal_table.add_column(justify="right")

        has_any_sensors = False

        if cpu_temp != -1.0:
            has_any_sensors = True
            t_color = (
                "red" if cpu_temp > 80.0 else ("yellow" if cpu_temp > 60.0 else "green")
            )
            thermal_table.add_row(
                Text("CPU Temperature:"),
                Text(f"{cpu_temp:.1f} °C", style=f"bold {t_color}"),
            )
        else:
            thermal_table.add_row(Text("CPU Temperature:"), Text("N/A", style="dim"))

        if gpu_temp != -1.0:
            has_any_sensors = True
            gt_color = (
                "red" if gpu_temp > 80.0 else ("yellow" if gpu_temp > 60.0 else "green")
            )
            thermal_table.add_row(
                Text("GPU Temperature:"),
                Text(f"{gpu_temp:.1f} °C", style=f"bold {gt_color}"),
            )
        else:
            thermal_table.add_row(Text("GPU Temperature:"), Text("N/A", style="dim"))

        if fan_speed != -1.0:
            has_any_sensors = True
            thermal_table.add_row(
                Text("Fan Speed:"),
                Text(f"{fan_speed:.0f} RPM", style="bold cyan"),
            )
        else:
            thermal_table.add_row(Text("Fan Speed:"), Text("N/A", style="dim"))

        if cpu_volt != -1.0:
            has_any_sensors = True
            thermal_table.add_row(
                Text("CPU Core Voltage:"),
                Text(f"{cpu_volt:.2f} V", style="bold yellow"),
            )
        else:
            thermal_table.add_row(Text("CPU Core Voltage:"), Text("N/A", style="dim"))

        thermal_content: Any
        if not has_any_sensors:
            thermal_content = Text(
                "\nNo LibreHardwareMonitor sensors detected\n"
                "(Not running LHM or N/A on macOS)",
                justify="center",
                style="dim",
            )
        else:
            thermal_content = thermal_table

        layout["thermals"].update(
            Panel(
                thermal_content,
                title="[bold yellow]Thermals & Fans[/bold yellow]",
                box=ROUNDED,
            )
        )

        # 7. RENDER ACTIVE ALERTS PANEL
        alert_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        alert_table.add_column(style="bold")
        alert_table.add_column(justify="center")
        alert_table.add_column(justify="right")
        alert_table.add_column(justify="right")

        has_active_alerts = False
        if self.dispatcher and self.dispatcher.active_incidents:
            alert_table.add_row(
                Text("Alert ID", style="dim"),
                Text("Status", style="dim"),
                Text("Current", style="dim"),
                Text("Limit", style="dim"),
            )
            for inc in self.dispatcher.active_incidents.values():
                has_active_alerts = True
                status_text = Text("FIRING", style="blink bold red")
                alert_table.add_row(
                    inc.rule.id,
                    status_text,
                    f"{inc.value:.1f}",
                    f"{inc.rule.threshold:.1f}",
                )

        if not has_active_alerts:
            alert_content: Any = Text(
                "\nNo Active Alerts (System Healthy)",
                justify="center",
                style="bold green",
            )
        else:
            alert_content = alert_table

        layout["alerts"].update(
            Panel(
                alert_content,
                title="[bold red]Active Alerts[/bold red]",
                box=ROUNDED,
            )
        )

        # 8. RENDER DIAGNOSTICS & SYSTEM METADATA
        specs_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        specs_table.add_column()
        specs_table.add_column(justify="right")

        collector_status = (
            Text("STALE/LAGGING", style="bold red")
            if is_stale
            else Text("ACTIVE", style="bold green")
        )
        specs_table.add_row(Text("Collector Status:"), collector_status)
        specs_table.add_row(
            Text("Cache Tick Age:"),
            Text(f"{health.age_s:.2f}s", style="red" if is_stale else "green"),
        )
        specs_table.add_row(
            Text("Cache Length:"), Text(f"{health.size}/{health.max_size}")
        )

        static_total_mem = self._get_metric_tag(
            metrics, "system.info.total_memory", "value", ""
        )
        if static_total_mem:
            cap_str = format_bytes(float(static_total_mem))
        else:
            cap_str = format_bytes(mem_total)
        specs_table.add_row(Text("Total RAM Capacity:"), Text(cap_str, style="dim"))

        layout["specs"].update(
            Panel(
                specs_table, title="[bold blue]Cache & Specs[/bold blue]", box=ROUNDED
            )
        )

    def run(self, refresh_rate: float = 1.0) -> None:
        """Run TUI monitor loop using Rich Live screen mode."""
        layout = self.generate_layout()

        # Configure Live rendering screen
        with Live(
            layout, console=self.console, screen=True, auto_refresh=False
        ) as live:
            try:
                while True:
                    self.render(layout)
                    live.update(layout, refresh=True)
                    time.sleep(refresh_rate)
            except KeyboardInterrupt:
                pass
