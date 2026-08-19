from __future__ import annotations

import time
from typing import Any

import pytest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.tray import MiniHud
from pc_diagnostic.gui.views.sensors_view import SensorsView
from pc_diagnostic.models import Snapshot

pytestmark = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


def test_missing_sensor_snapshot_degrades_without_exception(qtbot: Any) -> None:
    bridge = TelemetryBridge(RollingCache())
    sensors = SensorsView(bridge)
    hud = MiniHud(bridge)
    qtbot.addWidget(sensors)
    qtbot.addWidget(hud)
    empty_snapshot = Snapshot(timestamp=time.time(), readings=[])

    sensors._on_snapshot(empty_snapshot)
    hud.update_snapshot(empty_snapshot)

    assert sensors.core_grid.lbl_core_count.text() == "0 Cores"
    assert sensors.thermal_matrix.table.rowCount() == 0
    assert "No active fans" in sensors.fans_volts_card.lbl_no_fans.text()
    assert hud.cpu_label.text() == "CPU  N/A"
    assert hud.gpu_label.text() == "GPU  N/A"
    assert hud.temp_label.text() == "TEMP N/A"

