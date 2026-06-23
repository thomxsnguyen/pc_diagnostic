from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


def test_metric_reading_construction() -> None:
    reading = MetricReading(
        metric="cpu.utilization.total",
        value=42.0,
        unit=MetricUnit.PERCENT,
        source="test",
        tags={"tag1": "val1"},
    )
    assert reading.metric == "cpu.utilization.total"
    assert reading.value == 42.0
    assert reading.unit == MetricUnit.PERCENT
    assert reading.source == "test"
    assert reading.tags == {"tag1": "val1"}


def test_snapshot_construction() -> None:
    reading = MetricReading(
        metric="cpu.utilization.total",
        value=42.0,
        unit=MetricUnit.PERCENT,
        source="test",
    )
    snap = Snapshot(timestamp=12345.67, readings=[reading])
    assert snap.timestamp == 12345.67
    assert len(snap.readings) == 1
    assert snap.readings[0] == reading
