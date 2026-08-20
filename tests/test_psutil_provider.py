from unittest.mock import MagicMock, patch

import pytest

from pc_diagnostic.models import MetricUnit
from pc_diagnostic.providers.psutil_provider import PsutilProvider


def test_psutil_provider_uses_monotonic_uptime_fallback() -> None:
    mock_vm = MagicMock(total=16_000_000)
    with (
        patch.object(PsutilProvider, "_get_cpu_model", return_value="Test CPU"),
        patch.object(PsutilProvider, "_get_os_version", return_value="Test OS"),
        patch("psutil.virtual_memory", return_value=mock_vm),
        patch("psutil.boot_time", side_effect=PermissionError),
        patch("time.time", return_value=1000.0),
        patch("time.monotonic", return_value=250.0),
    ):
        provider = PsutilProvider()

    assert provider._boot_time == 750.0


def test_macos_memory_matches_activity_monitor_page_semantics() -> None:
    gib = 1024.0**3
    total = 24.0 * gib
    page_size = 16_384
    vm_stat = b"""Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                    10000.
Pages active:                                 400000.
Pages inactive:                               390000.
Pages speculative:                              1000.
Pages wired down:                             200000.
File-backed pages:                            250000.
Pages occupied by compressor:                 500000.
"""
    mock_vm = MagicMock(
        total=total,
        available=6.0 * gib,
        percent=75.0,
        wired=3.0 * gib,
    )
    provider = PsutilProvider.__new__(PsutilProvider)
    provider._total_memory = total

    with (
        patch("psutil.virtual_memory", return_value=mock_vm),
        patch("subprocess.check_output", return_value=vm_stat),
    ):
        memory = provider._get_mac_virtual_memory()

    expected_available = (10_000 + 1_000 + 250_000) * page_size
    expected_used = total - expected_available
    assert memory["available"] == expected_available
    assert memory["used"] == expected_used
    assert memory["percent"] == expected_used / total * 100.0
    assert memory["percent"] == pytest.approx(83.4, abs=0.1)


def test_macos_memory_falls_back_to_psutil_when_vm_stat_is_unavailable() -> None:
    gib = 1024.0**3
    mock_vm = MagicMock(
        total=24.0 * gib,
        available=6.0 * gib,
        percent=75.0,
        wired=3.0 * gib,
    )
    provider = PsutilProvider.__new__(PsutilProvider)
    provider._total_memory = mock_vm.total

    with (
        patch("psutil.virtual_memory", return_value=mock_vm),
        patch("subprocess.check_output", side_effect=OSError),
    ):
        memory = provider._get_mac_virtual_memory()

    assert memory["used"] == 18.0 * gib
    assert memory["available"] == 6.0 * gib
    assert memory["percent"] == 75.0


def test_psutil_provider_reads() -> None:
    # Set up mocks for psutil
    mock_vm = MagicMock()
    mock_vm.used = 8000000
    mock_vm.available = 8000000
    mock_vm.percent = 50.0
    mock_vm.total = 16000000

    mock_freq = MagicMock()
    mock_freq.current = 3200.0

    mock_part = MagicMock()
    mock_part.device = "/dev/sda1"
    mock_part.mountpoint = "/System/Volumes/Data"
    mock_part.opts = "rw"

    mock_usage = MagicMock()
    mock_usage.used = 50000000
    mock_usage.total = 100000000
    mock_usage.percent = 50.0

    mock_disk_io = MagicMock()
    mock_disk_io.read_bytes = 100000
    mock_disk_io.write_bytes = 200000

    mock_net_io = MagicMock()
    mock_net_io.bytes_sent = 50000
    mock_net_io.bytes_recv = 60000

    mock_proc = MagicMock()
    mock_proc.info = {"pid": 1234, "name": "python"}
    mock_proc.cpu_percent.return_value = 12.5
    mock_proc.memory_info.return_value.rss = 1024000

    def mock_cpu_percent(
        interval: float | None = None, percpu: bool = False
    ) -> float | list[float]:
        if percpu:
            return [20.0, 30.0]
        return 25.0

    # side_effect for time.time:
    # 1. __init__: self._start_time = 1000.0
    # 2. 1st read: now = 1001.0
    # 3. 2nd read: now = 1002.0
    time_mock = patch("time.time", side_effect=[1000.0, 1001.0, 1002.0])

    with (
        patch("psutil.virtual_memory", return_value=mock_vm),
        patch("psutil.boot_time", return_value=100.0),
        patch("psutil.cpu_percent", side_effect=mock_cpu_percent),
        patch("psutil.cpu_freq", return_value=mock_freq),
        patch("psutil.disk_partitions", return_value=[mock_part]),
        patch("psutil.disk_usage", return_value=mock_usage),
        patch("psutil.disk_io_counters", return_value={"disk0": mock_disk_io}),
        patch("psutil.net_io_counters", return_value={"en0": mock_net_io}),
        patch("psutil.process_iter", return_value=[mock_proc]),
        patch("platform.system", return_value="Darwin"),
        patch("platform.release", return_value="13.0"),
        time_mock,
        patch("subprocess.check_output", return_value=b"Intel Core i7"),
        patch.object(
            PsutilProvider,
            "_get_macos_storage_capacity",
            return_value=(100000000.0, 90000000.0),
        ),
    ):
        provider = PsutilProvider()
        assert provider.name == "psutil"
        assert provider.available() is True

        # First read triggers counters; rates will be missing since elapsed
        # calculation requires previous read values
        readings1 = provider.read()
        assert len(readings1) > 0

        # Update mock values to simulate throughput for 2nd read
        mock_disk_io.read_bytes = 150000
        mock_disk_io.write_bytes = 250000
        mock_net_io.bytes_sent = 60000
        mock_net_io.bytes_recv = 80000

        readings2 = provider.read()
        metrics2 = {r.metric: r for r in readings2}

        # Check rates
        assert metrics2["disk.usage.used"].value == 10000000.0
        assert metrics2["disk.usage.total"].value == 100000000.0
        assert metrics2["disk.usage.percent"].value == 10.0
        assert "disk.io.read_bytes" in metrics2
        assert (
            metrics2["disk.io.read_bytes"].value == 50000.0
        )  # (150000 - 100000) / 1.0
        assert metrics2["disk.io.read_bytes"].unit == MetricUnit.BYTES_PER_SEC

        assert "network.io.bytes_sent" in metrics2
        assert (
            metrics2["network.io.bytes_sent"].value == 10000.0
        )  # (60000 - 50000) / 1.0

        # Check static specs
        assert "system.info.cpu_model" in metrics2
        assert metrics2["system.info.cpu_model"].tags.get("value") == "Intel Core i7"
        assert metrics2["system.info.os_version"].tags.get("value") == "Darwin 13.0"
        assert metrics2["system.uptime"].value == 902.0
        assert metrics2["system.uptime"].unit == MetricUnit.SECONDS

        assert "process.cpu_percent" in metrics2
        assert metrics2["process.cpu_percent"].value == 12.5
        assert metrics2["process.cpu_percent"].tags.get("name") == "python"
