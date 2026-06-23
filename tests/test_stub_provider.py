from pc_diagnostic.models import MetricUnit
from pc_diagnostic.providers.stub import StubProvider


def test_stub_provider_metrics() -> None:
    provider = StubProvider()
    assert provider.name == "stub"
    assert provider.available() is True

    readings = provider.read()
    assert len(readings) == 3

    metrics = {r.metric: r for r in readings}

    assert "cpu.utilization.total" in metrics
    assert metrics["cpu.utilization.total"].unit == MetricUnit.PERCENT
    assert 0.0 <= metrics["cpu.utilization.total"].value <= 100.0

    assert "memory.utilization" in metrics
    assert metrics["memory.utilization"].unit == MetricUnit.PERCENT
    assert 0.0 <= metrics["memory.utilization"].value <= 100.0

    assert "system.uptime" in metrics
    assert metrics["system.uptime"].unit == MetricUnit.SECONDS
    assert metrics["system.uptime"].value >= 0.0
