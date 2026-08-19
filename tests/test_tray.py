from __future__ import annotations

from typing import Any

import pytest

from pc_diagnostic.alerts.models import AlertRule, Incident, IncidentState
from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.app import MainWindow
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.tray import MiniHud
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot

pytestmark = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


def _snapshot() -> Snapshot:
    return Snapshot(
        timestamp=10.0,
        readings=[
            MetricReading(
                "cpu.utilization.total", 42.0, MetricUnit.PERCENT, "test"
            ),
            MetricReading("memory.utilization", 61.0, MetricUnit.PERCENT, "test"),
            MetricReading(
                "system.temperature.cpu", 73.0, MetricUnit.CELSIUS, "test"
            ),
            MetricReading(
                "process.cpu_percent",
                25.0,
                MetricUnit.PERCENT,
                "test",
                {"name": "renderer", "pid": "12", "type": "cpu_top"},
            ),
        ],
    )


def test_mini_hud_displays_metrics_and_missing_gpu_as_na(qtbot: Any) -> None:
    bridge = TelemetryBridge(RollingCache())
    hud = MiniHud(bridge)
    qtbot.addWidget(hud)

    hud.update_snapshot(_snapshot())

    assert hud.cpu_label.text() == "CPU  42%"
    assert hud.ram_label.text() == "RAM  61%"
    assert hud.gpu_label.text() == "GPU  N/A"
    assert hud.temp_label.text() == "TEMP 73°C"
    assert "renderer" in hud.process_label.text()


def test_tray_menu_actions_and_diagnosis_route(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TelemetryBridge(RollingCache())
    window = MainWindow(bridge)
    qtbot.addWidget(window)
    manager = window.tray_manager
    actions = [action.text() for action in manager.menu.actions() if action.text()]
    assert actions == [
        "Open Dashboard",
        "Toggle Mini HUD",
        "Run AI Diagnosis",
        "Quit",
    ]

    called: list[bool] = []
    monkeypatch.setattr(
        window.diagnostics_view, "start_diagnosis", lambda: called.append(True)
    )
    manager.run_diagnosis()

    assert window.stack.currentIndex() == 4
    assert window.nav_buttons[4].isChecked()
    assert called == [True]


def test_firing_alert_uses_tray_notification(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TelemetryBridge(RollingCache())
    window = MainWindow(bridge)
    qtbot.addWidget(window)
    manager = window.tray_manager
    messages: list[tuple[Any, ...]] = []
    monkeypatch.setattr(manager.tray_icon, "isVisible", lambda: True)
    monkeypatch.setattr(
        manager.tray_icon, "showMessage", lambda *args: messages.append(args)
    )
    rule = AlertRule("high_cpu", "cpu", "gt", 90.0, 1.0, 5.0, 30.0)

    manager._on_alert(Incident(rule, IncidentState.FIRING, value=96.0))
    manager._on_alert(Incident(rule, IncidentState.PENDING, value=91.0))

    assert len(messages) == 1
    assert "high_cpu" in messages[0][1]

