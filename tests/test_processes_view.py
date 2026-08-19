import time
import unittest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.components.process_table import (
    NumericTableWidgetItem,
    ProcessTableWidget,
)
from pc_diagnostic.gui.views.processes_view import ProcessesView
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class TestProcessesView(unittest.TestCase):
    def setUp(self) -> None:
        if PYSIDE6_AVAILABLE:
            from PySide6.QtWidgets import QApplication

            self.app = QApplication.instance() or QApplication([])
        self.cache = RollingCache(maxlen=100)
        self.bridge = TelemetryBridge(self.cache)

    def test_numeric_table_widget_item_sorting(self) -> None:
        item1 = NumericTableWidgetItem(25.5, "25.5%")
        item2 = NumericTableWidgetItem(100.0, "100.0%")
        item3 = NumericTableWidgetItem(5.0, "5.0%")

        # 5.0 < 25.5 < 100.0 (whereas string sort would put "100.0" < "25.5" < "5.0")
        self.assertTrue(item3 < item1)
        self.assertTrue(item1 < item2)

    def test_process_table_widget_update_and_filter(self) -> None:
        widget = ProcessTableWidget()
        procs = [
            (101, "python3", 85.0, 450.0, "running"),
            (102, "Google Chrome", 12.5, 1250.0, "sleeping"),
            (103, "WindowServer", 22.0, 800.0, "running"),
        ]
        widget.update_processes(procs)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(widget.table.rowCount(), 3)
            self.assertEqual(widget.lbl_process_count.text(), "3 Processes")

            # Test search filtering by process name
            widget._on_search_changed("chrome")
            self.assertEqual(widget.lbl_process_count.text(), "1 Processes")
            for r in range(widget.table.rowCount()):
                name = widget.table.item(r, 1).text().lower()
                if "chrome" in name:
                    self.assertFalse(widget.table.isRowHidden(r))
                else:
                    self.assertTrue(widget.table.isRowHidden(r))

            # Test search filtering by PID
            widget._on_search_changed("101")
            self.assertEqual(widget.lbl_process_count.text(), "1 Processes")
            for r in range(widget.table.rowCount()):
                pid_str = widget.table.item(r, 0).text()
                if pid_str == "101":
                    self.assertFalse(widget.table.isRowHidden(r))
                else:
                    self.assertTrue(widget.table.isRowHidden(r))

            # Clear filter
            widget._on_search_changed("")
            self.assertEqual(widget.lbl_process_count.text(), "3 Processes")

    def test_processes_view_snapshot_and_pause(self) -> None:
        view = ProcessesView(self.bridge)

        readings = [
            MetricReading(
                metric="process.cpu_percent",
                value=78.5,
                unit=MetricUnit.PERCENT,
                source="test",
                tags={"pid": "444", "name": "blender", "type": "cpu_top"},
            ),
            MetricReading(
                metric="process.memory.used",
                value=2048 * 1024 * 1024,
                unit=MetricUnit.BYTES,
                source="test",
                tags={
                    "pid": "555",
                    "name": "docker",
                    "type": "mem_top",
                    "mem_str": "2.0 GB",
                },
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)
        view._on_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertIn("blender", view.lbl_top_cpu.text())
            self.assertIn("78.5%", view.lbl_top_cpu.text())
            self.assertIn("docker", view.lbl_top_mem.text())

            # Test toggle pause
            self.assertFalse(view._is_paused)
            view._toggle_pause()
            self.assertTrue(view._is_paused)
            self.assertEqual(view.btn_pause.text(), "Resume")
            view._toggle_pause()
            self.assertFalse(view._is_paused)


if __name__ == "__main__":
    unittest.main()
