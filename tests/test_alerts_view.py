import time
import unittest

from pc_diagnostic.alerts.models import AlertRule, Incident, IncidentState
from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.views.alerts_view import AlertsView


class TestAlertsView(unittest.TestCase):
    def setUp(self) -> None:
        if PYSIDE6_AVAILABLE:
            from PySide6.QtWidgets import QApplication

            self.app = QApplication.instance() or QApplication([])
        self.cache = RollingCache(maxlen=100)
        self.bridge = TelemetryBridge(self.cache)

    def test_alerts_view_sliders(self) -> None:
        view = AlertsView(self.bridge)

        view._on_cpu_slider_changed(85)
        self.assertEqual(view.cpu_threshold, 85.0)

        view._on_mem_slider_changed(80)
        self.assertEqual(view.mem_threshold, 80.0)

        view._on_debounce_slider_changed(10)
        self.assertEqual(view.debounce_s, 10.0)

        view._on_hysteresis_slider_changed(8)
        self.assertEqual(view.hysteresis, 8.0)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(view.lbl_cpu_val.text(), "85%")
            self.assertEqual(view.lbl_mem_val.text(), "80%")
            self.assertEqual(view.lbl_debounce_val.text(), "10s")
            self.assertEqual(view.lbl_hysteresis_val.text(), "8%")

    def test_alerts_view_incident_table_update(self) -> None:
        view = AlertsView(self.bridge)

        rule = AlertRule(
            id="high_cpu",
            metric="cpu.utilization.total",
            condition="gt",
            threshold=90.0,
            duration_s=5.0,
            hysteresis_offset=10.0,
            cooldown_s=60.0,
        )
        incident = Incident(
            rule=rule,
            state=IncidentState.FIRING,
            first_triggered_at=time.time(),
            last_fired_at=time.time(),
            value=96.4,
        )

        view._on_alert_triggered(incident)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(view.incidents_table.rowCount(), 1)
            self.assertEqual(view.incidents_table.item(0, 1).text(), "high_cpu")
            self.assertEqual(view.incidents_table.item(0, 2).text(), "FIRING")
            self.assertEqual(view.incidents_table.item(0, 3).text(), "96.4")
            self.assertEqual(view.incidents_table.item(0, 4).text(), "90.0")

            # Test clearing
            view._clear_incidents()
            self.assertEqual(view.incidents_table.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
