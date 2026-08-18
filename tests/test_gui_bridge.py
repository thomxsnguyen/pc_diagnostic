import time
import unittest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import TelemetryBridge
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class TestTelemetryBridge(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = RollingCache(maxlen=100)
        self.bridge = TelemetryBridge(self.cache)

    def test_bridge_cache_property(self) -> None:
        self.assertEqual(self.bridge.cache, self.cache)
        self.assertIsNone(self.bridge.dispatcher)

    def test_bridge_getters(self) -> None:
        reading = MetricReading(
            metric="cpu.utilization.total",
            value=45.2,
            unit=MetricUnit.PERCENT,
            source="test",
        )
        snap = Snapshot(timestamp=time.time(), readings=[reading])
        self.cache.push(snap)

        latest = self.bridge.get_latest_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.timestamp, snap.timestamp)

        series = self.bridge.get_series("cpu.utilization.total", 10)
        self.assertEqual(series, [45.2])

        health = self.bridge.get_health()
        self.assertEqual(health.size, 1)

    def test_bridge_on_tick_signals(self) -> None:
        received_snapshots = []
        received_health = []
        received_status = []

        self.bridge.snapshot_updated.connect(lambda s: received_snapshots.append(s))
        self.bridge.cache_health_changed.connect(lambda h: received_health.append(h))
        self.bridge.collector_status_changed.connect(
            lambda st: received_status.append(st)
        )

        reading = MetricReading(
            metric="memory.utilization",
            value=60.0,
            unit=MetricUnit.PERCENT,
            source="test",
        )
        snap = Snapshot(timestamp=time.time(), readings=[reading])
        self.cache.push(snap)

        # Trigger tick
        self.bridge._on_tick()

        self.assertEqual(len(received_snapshots), 1)
        self.assertEqual(len(received_health), 1)
        self.assertEqual(len(received_status), 1)
        self.assertTrue(received_status[0])  # Should be healthy

    def test_bridge_emit_diagnosis(self) -> None:
        received_reports = []
        self.bridge.diagnosis_completed.connect(lambda r: received_reports.append(r))
        self.bridge.emit_diagnosis("# Diagnosis Report")

        self.assertEqual(received_reports, ["# Diagnosis Report"])

    def test_bridge_update_rule_threshold(self) -> None:
        self.bridge.update_rule_threshold("high_memory", threshold=50.0, duration_s=1.0)
        rule = next(r for r in self.bridge.evaluator.rules if r.id == "high_memory")
        self.assertEqual(rule.threshold, 50.0)
        self.assertEqual(rule.duration_s, 1.0)


if __name__ == "__main__":
    unittest.main()
