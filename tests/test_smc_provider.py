import subprocess
from unittest.mock import MagicMock, patch

from pc_diagnostic.models import MetricUnit
from pc_diagnostic.providers.smc_provider import SmcProvider


def test_smc_provider_availability() -> None:
    provider = SmcProvider()
    with patch("sys.platform", "darwin"), patch("os.path.exists", return_value=True):
        assert provider.available() is True
    with patch("sys.platform", "win32"):
        assert provider.available() is False


def test_smc_provider_compile_missing() -> None:
    with (
        patch("sys.platform", "darwin"),
        patch("os.path.exists", return_value=False),
        patch("subprocess.run") as mock_run,
    ):
        SmcProvider()
        assert mock_run.call_count == 1
        # First call is compile
        args = mock_run.call_args[0][0]
        assert "clang" in args
        assert "-framework" in args


def test_smc_provider_read_success() -> None:

    provider = SmcProvider()
    # Mock availability and subprocess read call
    mock_run_res = MagicMock()
    mock_run_res.stdout = (
        '[{"sensor":"PMU tdie1","type":"Temperature","value":45.5},'
        '{"sensor":"PMU tdev2","type":"Temperature","value":50.1},'
        '{"sensor":"Fan 0 Speed","type":"Fan","value":1500.0},'
        '{"sensor":"unmapped sensor","type":"Temperature","value":99.0}]'
    )

    with (
        patch.object(provider, "available", return_value=True),
        patch("subprocess.run", return_value=mock_run_res),
    ):
        readings = provider.read()

        # Should map:
        # PMU tdie1 -> system.temperature.cpu (Celsius)
        # PMU tdev2 -> system.temperature.gpu (Celsius)
        # Fan 0 Speed -> system.fan.speed (RPM)
        # unmapped sensor -> simply absent

        cpu = [r for r in readings if r.metric == "system.temperature.cpu"]
        assert len(cpu) == 1
        assert cpu[0].value == 45.5
        assert cpu[0].unit == MetricUnit.CELSIUS

        gpu = [r for r in readings if r.metric == "system.temperature.gpu"]
        assert len(gpu) == 1
        assert gpu[0].value == 50.1
        assert gpu[0].unit == MetricUnit.CELSIUS

        fan = [r for r in readings if r.metric == "system.fan.speed"]
        assert len(fan) == 1
        assert fan[0].value == 1500.0
        assert fan[0].unit == MetricUnit.RPM

        # Verify unmapped sensor is omitted
        unmapped = [r for r in readings if r.tags.get("sensor") == "unmapped sensor"]
        assert len(unmapped) == 0


def test_smc_provider_timeout() -> None:
    provider = SmcProvider()
    with (
        patch.object(provider, "available", return_value=True),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=[], timeout=1.0),
        ),
    ):
        readings = provider.read()
        assert readings == []


def test_smc_provider_exec_error() -> None:
    provider = SmcProvider()
    with (
        patch.object(provider, "available", return_value=True),
        patch("subprocess.run", side_effect=RuntimeError("exec error")),
    ):
        readings = provider.read()
        assert readings == []
