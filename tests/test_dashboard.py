from pc_diagnostic.cache import RollingCache
from pc_diagnostic.dashboard import (
    TerminalDashboard,
    format_bytes,
    format_rate,
    get_bar_style,
)
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


def test_format_helpers() -> None:
    # Test byte formatting
    assert format_bytes(500) == "500.0 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(1024 * 1024 * 3.5) == "3.5 MB"
    assert format_bytes(1024 * 1024 * 1024 * 1.2) == "1.2 GB"

    # Test throughput rate formatting
    assert format_rate(1024) == "1.0 KB/s"

    # Test style thresholds
    assert get_bar_style(20.0) == "bold green"
    assert get_bar_style(60.0) == "bold yellow"
    assert get_bar_style(90.0) == "bold red"


def test_dashboard_render_empty() -> None:
    cache = RollingCache(maxlen=10)
    dashboard = TerminalDashboard(cache)
    layout = dashboard.generate_layout()

    # Render with empty cache should execute without errors
    dashboard.render(layout)
    assert layout["header"].renderable is not None


def test_dashboard_render_populated() -> None:
    cache = RollingCache(maxlen=10)
    dashboard = TerminalDashboard(cache)
    layout = dashboard.generate_layout()

    # Build mock metrics snapshot
    readings = [
        MetricReading("cpu.utilization.total", 45.0, MetricUnit.PERCENT, "psutil"),
        MetricReading(
            "cpu.utilization.per_core",
            30.0,
            MetricUnit.PERCENT,
            "psutil",
            {"core": "0"},
        ),
        MetricReading(
            "cpu.utilization.per_core",
            60.0,
            MetricUnit.PERCENT,
            "psutil",
            {"core": "1"},
        ),
        MetricReading(
            "cpu.frequency.current", 2400000000.0, MetricUnit.HERTZ, "psutil"
        ),
        MetricReading("memory.used", 4000000000.0, MetricUnit.BYTES, "psutil"),
        MetricReading("memory.available", 12000000000.0, MetricUnit.BYTES, "psutil"),
        MetricReading("memory.utilization", 25.0, MetricUnit.PERCENT, "psutil"),
        MetricReading(
            "disk.usage.used",
            50000000000.0,
            MetricUnit.BYTES,
            "psutil",
            {"device": "/dev/sda1", "mountpoint": "/"},
        ),
        MetricReading(
            "disk.io.read_bytes",
            1024.0,
            MetricUnit.BYTES_PER_SEC,
            "psutil",
            {"device": "disk0"},
        ),
        MetricReading(
            "disk.io.write_bytes",
            2048.0,
            MetricUnit.BYTES_PER_SEC,
            "psutil",
            {"device": "disk0"},
        ),
        MetricReading(
            "network.io.bytes_sent",
            512.0,
            MetricUnit.BYTES_PER_SEC,
            "psutil",
            {"interface": "en0"},
        ),
        MetricReading(
            "network.io.bytes_recv",
            1024.0,
            MetricUnit.BYTES_PER_SEC,
            "psutil",
            {"interface": "en0"},
        ),
        MetricReading(
            "process.cpu_percent",
            5.0,
            MetricUnit.PERCENT,
            "psutil",
            {"pid": "100", "name": "system"},
        ),
        MetricReading(
            "process.memory.used",
            100000000.0,
            MetricUnit.BYTES,
            "psutil",
            {"pid": "100", "name": "system"},
        ),
        MetricReading(
            "system.info.cpu_model",
            0.0,
            MetricUnit.INFO,
            "psutil",
            {"value": "Intel CPU"},
        ),
        MetricReading(
            "system.info.os_version",
            0.0,
            MetricUnit.INFO,
            "psutil",
            {"value": "macOS 13"},
        ),
        MetricReading(
            "system.info.total_memory",
            0.0,
            MetricUnit.INFO,
            "psutil",
            {"value": "16000000000"},
        ),
    ]
    cache.push(Snapshot(timestamp=1783486314.0, readings=readings))

    # Render should populate layout panel renderables
    dashboard.render(layout)
    assert layout["header"].renderable is not None
    assert layout["cpu"].renderable is not None
    assert layout["memory"].renderable is not None
    assert layout["io"].renderable is not None
    assert layout["processes"].renderable is not None
    assert layout["specs"].renderable is not None


def test_generate_sparkline() -> None:
    cache = RollingCache(maxlen=10)
    dashboard = TerminalDashboard(cache)

    # 1. Empty cache sparkline should return empty space characters
    assert dashboard.generate_sparkline("cpu.util", max_val=100.0, n=5) == "     "

    # 2. Populated cache should return correct sparkline blocks
    for idx, val in enumerate([0.0, 20.0, 50.0, 80.0, 100.0]):
        cache.push(
            Snapshot(
                timestamp=float(100 + idx),
                readings=[MetricReading("cpu.util", val, MetricUnit.PERCENT, "test")],
            )
        )

    sparkline = dashboard.generate_sparkline("cpu.util", max_val=100.0, n=5)
    # expected block indices for values [0, 20, 50, 80, 100] are:
    # 0.0 -> 0.0 * 7 = 0 -> " "
    # 0.2 -> 0.2 * 7 = 1 -> "▂"
    # 0.5 -> 0.5 * 7 = 3 -> "▄"
    # 0.8 -> 0.8 * 7 = 5 -> "▆"
    # 1.0 -> 1.0 * 7 = 7 -> "█"
    assert len(sparkline) == 5
    assert sparkline == " ▂▄▆█"
