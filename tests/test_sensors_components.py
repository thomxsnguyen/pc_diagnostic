import time
import unittest

from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE
from pc_diagnostic.gui.components import (
    FansVoltagesCard,
    PerCoreGridWidget,
    ThermalMatrixWidget,
)
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class TestSensorsComponents(unittest.TestCase):
    def test_per_core_grid_update(self) -> None:
        grid = PerCoreGridWidget()
        readings = [
            MetricReading(
                metric="cpu.utilization.core.0",
                value=25.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="cpu.utilization.core.1",
                value=85.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="cpu.utilization.core.2",
                value=55.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="cpu.utilization.core.3",
                value=10.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)
        grid.update_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(grid.lbl_core_count.text(), "4 Cores")
            self.assertEqual(len(grid._cores), 4)
            self.assertEqual(grid._cores[0].lbl_val.text(), "25.0%")
            self.assertEqual(grid._cores[1].lbl_val.text(), "85.0%")

    def test_thermal_matrix_min_max_and_grouping(self) -> None:
        matrix = ThermalMatrixWidget()

        # Snapshot 1
        readings1 = [
            MetricReading(
                metric="thermal.cpu.package_temp",
                value=50.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
            MetricReading(
                metric="thermal.gpu.temp",
                value=68.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
        ]
        snap1 = Snapshot(timestamp=time.time(), readings=readings1)
        matrix.update_snapshot(snap1)

        # Snapshot 2 (Higher CPU, Lower GPU)
        readings2 = [
            MetricReading(
                metric="thermal.cpu.package_temp",
                value=90.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
            MetricReading(
                metric="thermal.gpu.temp",
                value=60.0,
                unit=MetricUnit.CELSIUS,
                source="test",
            ),
        ]
        snap2 = Snapshot(timestamp=time.time(), readings=readings2)
        matrix.update_snapshot(snap2)

        if PYSIDE6_AVAILABLE:
            cpu_stat = matrix._sensors["thermal.cpu.package_temp"]
            self.assertEqual(cpu_stat["group"], "CPU")
            self.assertEqual(cpu_stat["min"], 50.0)
            self.assertEqual(cpu_stat["max"], 90.0)
            self.assertEqual(cpu_stat["current"], 90.0)

            gpu_stat = matrix._sensors["thermal.gpu.temp"]
            self.assertEqual(gpu_stat["group"], "GPU")
            self.assertEqual(gpu_stat["min"], 60.0)
            self.assertEqual(gpu_stat["max"], 68.0)
            self.assertEqual(gpu_stat["current"], 60.0)

            # Check status column (row for CPU should be HOT)
            self.assertEqual(matrix.table.item(cpu_stat["row"], 5).text(), "HOT")
            self.assertEqual(matrix.table.item(gpu_stat["row"], 5).text(), "NORMAL")

    def test_fans_voltages_card_update(self) -> None:
        card = FansVoltagesCard()
        readings = [
            MetricReading(
                metric="fan.speed.0",
                value=1850.0,
                unit=MetricUnit.RPM,
                source="test",
                tags={"fan": "CPU Fan"},
            ),
            MetricReading(
                metric="voltage.cpu.core",
                value=1.18,
                unit=MetricUnit.VOLTS,
                source="test",
            ),
            MetricReading(
                metric="voltage.12v", value=12.08, unit=MetricUnit.VOLTS, source="test"
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)
        card.update_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertFalse(card.lbl_no_fans.isVisible())
            self.assertFalse(card.lbl_no_volts.isVisible())
            self.assertIn("fan.speed.0", card._fans)
            self.assertEqual(card._fans["fan.speed.0"][0].text(), "1850 RPM")
            self.assertEqual(card._voltages["voltage.cpu.core"].text(), "1.18 V")
            self.assertEqual(card._voltages["voltage.12v"].text(), "12.08 V")


if __name__ == "__main__":
    unittest.main()
