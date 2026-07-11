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
    def __init__(self, cache: RollingCache) -> None:
        self.cache = cache
        self.console = Console()

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
            Layout(name="processes", ratio=6), Layout(name="specs", ratio=3)
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

        # 1. RENDER HEADER
        last_update_str = time.strftime("%H:%M:%S", time.localtime(latest.timestamp))
        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left")
        header_table.add_column(justify="center")
        header_table.add_column(justify="right")

        # CPU model & OS specs for header (retrieve from static specs)
        cpu_model = "Unknown CPU"
        if "system.info.cpu_model" in metrics:
            cpu_model = metrics["system.info.cpu_model"][0].tags.get(
                "value", "Unknown CPU"
            )
        os_version = "Unknown OS"
        if "system.info.os_version" in metrics:
            os_version = metrics["system.info.os_version"][0].tags.get(
                "value", "Unknown OS"
            )

        header_table.add_row(
            Text(f" OS: {os_version}", style="bold cyan"),
            Text(
                "💻 PC DIAGNOSTIC LIVE TUI MONITOR 💻",
                style="bold white on blue",
            ),
            Text(
                f"Last Tick: {last_update_str} | "
                f"Cache: {health.size}/{health.max_size} ",
                style="bold green",
            ),
        )
        layout["header"].update(Panel(header_table, box=ROUNDED, style="blue"))

        # 2. RENDER CPU PANEL
        cpu_pct = 0.0
        if "cpu.utilization.total" in metrics:
            cpu_pct = metrics["cpu.utilization.total"][0].value

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
                        bar_width=12, complete_style=c_style2, finished_style=c_style2
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
                cores_table.add_row(f"Core {core_id1}: {c_pct1:4.1f}%", prog1, "", "")

        cpu_freq_str = "Unknown Freq"
        if "cpu.frequency.current" in metrics:
            freq_hz = metrics["cpu.frequency.current"][0].value
            cpu_freq_str = f"{freq_hz / 1_000_000.0:.0f} MHz"

        cpu_content = Table.grid(expand=True)
        cpu_content.add_row(cpu_progress.get_renderable())
        cpu_content.add_row(
            Text(f"CPU Model: {cpu_model} ({cpu_freq_str})", style="dim")
        )
        cpu_content.add_row(Text("-" * 50, style="dim"))
        cpu_content.add_row(cores_table)
        layout["cpu"].update(
            Panel(
                cpu_content, title="[bold cyan]CPU Utilization[/bold cyan]", box=ROUNDED
            )
        )

        # 3. RENDER MEMORY PANEL
        mem_pct = 0.0
        mem_used = 0.0
        mem_avail = 0.0
        if "memory.utilization" in metrics:
            mem_pct = metrics["memory.utilization"][0].value
        if "memory.used" in metrics:
            mem_used = metrics["memory.used"][0].value
        if "memory.available" in metrics:
            mem_avail = metrics["memory.available"][0].value
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

        mem_content = Table.grid(expand=True)
        mem_content.add_row(mem_progress.get_renderable())
        mem_content.add_row(
            Text(f"Available RAM: {format_bytes(mem_avail)}", style="dim")
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
        storage_info.add_row(Text("📁 Storage Usage", style="bold yellow"), "")

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
            storage_info.add_row(Text("  No storage data"), "")

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
        network_info.add_row(Text("📶 Network I/O", style="bold magenta"), "")
        network_info.add_row(
            Text("  Upload (Tx):"), Text(format_rate(net_sent), style="bold magenta")
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
        proc_table = Table(box=None, padding=(0, 1), expand=True)
        proc_table.add_column("PID", style="dim", justify="right")
        proc_table.add_column("Name", style="bold")
        proc_table.add_column("CPU %", justify="right")
        proc_table.add_column("Memory (RSS)", justify="right")

        proc_cpus = metrics.get("process.cpu_percent", [])
        proc_mems = metrics.get("process.memory.used", [])

        # Build process map by PID for display
        proc_map: dict[str, dict[str, Any]] = {}
        for r in proc_cpus:
            pid = r.tags.get("pid", "0")
            name = r.tags.get("name", "unknown")
            proc_map[pid] = {"pid": pid, "name": name, "cpu": r.value, "mem": 0.0}
        for r in proc_mems:
            pid = r.tags.get("pid", "0")
            if pid in proc_map:
                proc_map[pid]["mem"] = r.value

        # Sort by CPU utilization
        sorted_procs = sorted(proc_map.values(), key=lambda x: x["cpu"], reverse=True)
        for p in sorted_procs:
            c_style = (
                "red" if p["cpu"] > 30.0 else ("yellow" if p["cpu"] > 10.0 else "green")
            )
            proc_table.add_row(
                p["pid"],
                p["name"],
                Text(f"{p['cpu']:.1f}%", style=c_style),
                format_bytes(p["mem"]),
            )

        layout["processes"].update(
            Panel(
                proc_table, title="[bold red]Top CPU Processes[/bold red]", box=ROUNDED
            )
        )

        # 6. RENDER DIAGNOSTICS & SYSTEM METADATA
        specs_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        specs_table.add_column()
        specs_table.add_column(justify="right")

        specs_table.add_row(
            Text("Collector Status:"), Text("ACTIVE", style="bold green")
        )
        specs_table.add_row(
            Text("Cache Tick Age:"),
            Text(
                f"{health.age_s:.2f}s", style="green" if health.age_s < 2.0 else "red"
            ),
        )
        specs_table.add_row(
            Text("Cache Length:"), Text(f"{health.size}/{health.max_size}")
        )
        specs_table.add_row(
            Text("Total RAM Capacity:"), Text(format_bytes(mem_total), style="dim")
        )

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
