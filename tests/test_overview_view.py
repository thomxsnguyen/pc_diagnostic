import time
import unittest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.views.overview_view import OverviewView
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class TestOverviewView(unittest.TestCase):
    def setUp(self) -> None:
        if PYSIDE6_AVAILABLE:
            from PySide6.QtWidgets import QApplication

            self.app = QApplication.instance() or QApplication([])
        self.cache = RollingCache(maxlen=100)
        self.bridge = TelemetryBridge(self.cache)

    def test_overview_view_init_and_snapshot_update(self) -> None:
        view = OverviewView(self.bridge)

        readings = [
            MetricReading(
                metric="cpu.utilization.total",
                value=42.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="cpu.frequency.current",
                value=3200 * 1e6,
                unit=MetricUnit.HERTZ,
                source="test",
            ),
            MetricReading(
                metric="system.info.cpu_model",
                value=0.0,
                unit=MetricUnit.INFO,
                source="test",
                tags={
                    "value": (
                        '{"SPHardwareDataType":[{"chip_type":"Apple M1 Max",'
                        '"serial_number":"hidden"}]}'
                    )
                },
            ),
            MetricReading(
                metric="memory.utilization",
                value=55.5,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="memory.used",
                value=16 * (1024**3),
                unit=MetricUnit.BYTES,
                source="test",
            ),
            MetricReading(
                metric="memory.total",
                value=32 * (1024**3),
                unit=MetricUnit.BYTES,
                source="test",
            ),
            MetricReading(
                metric="thermal.cpu.temp",
                value=48.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
            MetricReading(
                metric="system.info.os_version",
                value=0.0,
                unit=MetricUnit.INFO,
                source="test",
                tags={"value": "Darwin 25.5.0 (Darwin Kernel Version details)"},
            ),
            MetricReading(
                metric="system.uptime",
                value=7200.0,
                unit=MetricUnit.SECONDS,
                source="test",
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)

        # Trigger snapshot
        view._on_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(view.cpu_gauge.value, 42.0)
            self.assertEqual(view.mem_gauge.value, 55.5)
            self.assertEqual(view.thermal_gauge.value, 48.0)
            self.assertEqual(view.lbl_cpu_model.text(), "Apple M1 Max")
            self.assertEqual(view.lbl_os.text(), "Darwin 25.5.0")
            self.assertIn("2h 0m", view.lbl_uptime.text())
            self.assertIn("32.0 GB", view.lbl_mem_total.text())



if __name__ == "__main__":
    unittest.main()
