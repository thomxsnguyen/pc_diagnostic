import time
import unittest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.views.sensors_view import SensorsView
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class TestSensorsView(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = RollingCache(maxlen=100)
        self.bridge = TelemetryBridge(self.cache)

    def test_sensors_view_init_and_snapshot_update(self) -> None:
        view = SensorsView(self.bridge)

        readings = [
            MetricReading(
                metric="cpu.utilization.core.0",
                value=33.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="cpu.utilization.core.1",
                value=66.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="thermal.cpu.temp",
                value=52.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
            MetricReading(
                metric="thermal.gpu.temp",
                value=45.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
            MetricReading(
                metric="fan.speed.0", value=1200.0, unit=MetricUnit.RPM, source="test"
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)

        # Trigger snapshot
        view._on_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(len(view.core_grid._cores), 2)
            self.assertIn("thermal.cpu.temp", view.thermal_matrix._sensors)
            self.assertEqual(
                view.thermal_matrix._sensors["thermal.cpu.temp"]["current"], 52.0
            )
            self.assertIn("fan.speed.0", view.fans_volts_card._fans)


if __name__ == "__main__":
    unittest.main()
