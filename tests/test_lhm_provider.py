import subprocess
from unittest.mock import MagicMock, patch

from pc_diagnostic.models import MetricUnit
from pc_diagnostic.providers.lhm_provider import LhmProvider


def test_lhm_provider_availability() -> None:
    provider = LhmProvider()
    with patch("sys.platform", "win32"):
        assert provider.available() is True
    with patch("sys.platform", "darwin"):
        assert provider.available() is False


def test_lhm_provider_read_success() -> None:
    mock_payload = [
        {
            "Name": "CPU Core",
            "SensorType": "Temperature",
            "Value": 55.4,
            "Identifier": "/intelcpu/0/temperature/0",
        },
        {
            "Name": "GPU Core",
            "SensorType": "Temperature",
            "Value": 60.1,
            "Identifier": "/nvidiagpu/0/temperature/0",
        },
        {
            "Name": "Other Temp",
            "SensorType": "Temperature",
            "Value": 35.0,
            "Identifier": "/other/temperature/0",
        },
        {
            "Name": "Fan #1",
            "SensorType": "Fan",
            "Value": 1200.0,
            "Identifier": "/lpc/nct6779d/fan/0",
        },
        {
            "Name": "CPU VCore",
            "SensorType": "Voltage",
            "Value": 1.21,
            "Identifier": "/intelcpu/0/voltage/0",
        },
        {
            "Name": "Other Volt",
            "SensorType": "Voltage",
            "Value": 3.3,
            "Identifier": "/lpc/nct6779d/voltage/0",
        },
    ]

    provider = LhmProvider()
    with patch.object(provider, "_query_wmi", return_value=mock_payload):
        readings = provider.read()

        # Verify CPU temp
        cpu_temp = [r for r in readings if r.metric == "system.temperature.cpu"]
        assert len(cpu_temp) == 1
        assert cpu_temp[0].value == 55.4
        assert cpu_temp[0].unit == MetricUnit.CELSIUS
        assert cpu_temp[0].tags["sensor"] == "CPU Core"

        # Verify GPU temp
        gpu_temp = [r for r in readings if r.metric == "system.temperature.gpu"]
        assert len(gpu_temp) == 1
        assert gpu_temp[0].value == 60.1

        # Verify other temp
        other_temp = [r for r in readings if r.metric == "system.temperature.other"]
        assert len(other_temp) == 1
        assert other_temp[0].value == 35.0

        # Verify Fan speed
        fan = [r for r in readings if r.metric == "system.fan.speed"]
        assert len(fan) == 1
        assert fan[0].value == 1200.0
        assert fan[0].unit == MetricUnit.RPM

        # Verify CPU Volt
        cpu_volt = [r for r in readings if r.metric == "system.voltage.cpu"]
        assert len(cpu_volt) == 1
        assert cpu_volt[0].value == 1.21
        assert cpu_volt[0].unit == MetricUnit.VOLTS

        # Verify other Volt
        other_volt = [r for r in readings if r.metric == "system.voltage.other"]
        assert len(other_volt) == 1
        assert other_volt[0].value == 3.3


def test_lhm_provider_query_wmi_success() -> None:
    mock_run_res = MagicMock()
    mock_run_res.stdout = (
        '[{"Name":"CPU","SensorType":"Temperature","Value":50.0,"Identifier":"/cpu/0"}]'
    )

    provider = LhmProvider()
    with patch("subprocess.run", return_value=mock_run_res):
        res = provider._query_wmi()
        assert len(res) == 1
        assert res[0]["Name"] == "CPU"
        assert res[0]["Value"] == 50.0


def test_lhm_provider_query_wmi_timeout() -> None:
    provider = LhmProvider()
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=1.0),
    ):
        res = provider._query_wmi()
        assert res == []


def test_lhm_provider_query_wmi_error() -> None:
    provider = LhmProvider()
    with patch("subprocess.run", side_effect=RuntimeError("Subprocess failed")):
        res = provider._query_wmi()
        assert res == []
