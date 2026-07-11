from unittest.mock import MagicMock, patch

from pc_diagnostic.models import MetricUnit
from pc_diagnostic.providers.psutil_provider import PsutilProvider


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
    mock_part.mountpoint = "/"
    mock_part.opts = "rw"

    mock_usage = MagicMock()
    mock_usage.used = 50000000

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
        patch("psutil.cpu_percent", side_effect=mock_cpu_percent),
        patch("psutil.cpu_freq", return_value=mock_freq),
        patch("psutil.disk_partitions", return_value=[mock_part]),
        patch("psutil.disk_usage", return_value=mock_usage),
        patch("psutil.disk_io_counters", return_value={"disk0": mock_disk_io}),
        patch("psutil.net_io_counters", return_value={"en0": mock_net_io}),
        patch("psutil.process_iter", return_value=[mock_proc]),
        patch("platform.system", return_value="Darwin"),
        patch("platform.release", return_value="13.0"),
        patch("platform.version", return_value="Release 13.0"),
        time_mock,
        patch("subprocess.check_output", return_value=b"Intel Core i7"),
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

        assert "process.cpu_percent" in metrics2
        assert metrics2["process.cpu_percent"].value == 12.5
        assert metrics2["process.cpu_percent"].tags.get("name") == "python"
