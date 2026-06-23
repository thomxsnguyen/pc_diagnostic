from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.normalizer import Normalizer


def test_normalizer_valid_readings() -> None:
    readings = [
        MetricReading(
            metric="cpu.utilization.total",
            value=25.5,
            unit=MetricUnit.PERCENT,
            source="test_src",
        ),
        MetricReading(
            metric="memory.used",
            value=1024.0,
            unit=MetricUnit.BYTES,
            source="test_src",
            tags={"device": "ram"},
        ),
    ]

    valid, dropped = Normalizer.validate(readings)
    assert len(valid) == 2
    assert dropped == 0
    assert valid[0].metric == "cpu.utilization.total"
    assert valid[1].tags == {"device": "ram"}


def test_normalizer_invalid_names() -> None:
    readings = [
        # Invalid naming format (no dots)
        MetricReading(
            metric="cpu_utilization",
            value=25.5,
            unit=MetricUnit.PERCENT,
            source="test_src",
        ),
        # Empty name
        MetricReading(
            metric="",
            value=25.5,
            unit=MetricUnit.PERCENT,
            source="test_src",
        ),
    ]

    valid, dropped = Normalizer.validate(readings)
    assert len(valid) == 0
    assert dropped == 2


def test_normalizer_non_finite_values() -> None:
    readings = [
        MetricReading(
            metric="cpu.utilization",
            value=float("nan"),
            unit=MetricUnit.PERCENT,
            source="test_src",
        ),
        MetricReading(
            metric="memory.used",
            value=float("inf"),
            unit=MetricUnit.BYTES,
            source="test_src",
        ),
    ]

    valid, dropped = Normalizer.validate(readings)
    assert len(valid) == 0
    assert dropped == 2


def test_normalizer_empty_source() -> None:
    readings = [
        MetricReading(
            metric="cpu.utilization",
            value=25.5,
            unit=MetricUnit.PERCENT,
            source="",
        ),
    ]

    valid, dropped = Normalizer.validate(readings)
    assert len(valid) == 0
    assert dropped == 1
