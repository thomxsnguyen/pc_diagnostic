from __future__ import annotations

from typing import Any

import pytest

from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE
from pc_diagnostic.gui.components import RadialGaugeWidget, TimeSeriesChart

pytestmark = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


def test_radial_gauge_renders_empty_and_clamps_extremes(qtbot: Any) -> None:
    gauge = RadialGaugeWidget()
    qtbot.addWidget(gauge)
    gauge.resize(180, 180)

    assert not gauge.grab().isNull()
    gauge.set_value(-10_000.0)
    assert gauge.value == 0.0
    gauge.set_value(10_000.0)
    assert gauge.value == 100.0
    assert not gauge.grab().isNull()


def test_timeseries_chart_renders_empty_and_extreme_data(qtbot: Any) -> None:
    chart = TimeSeriesChart(maxlen=60)
    qtbot.addWidget(chart)
    chart.resize(900, 260)

    assert not chart.grab().isNull()
    for value in (-10_000.0, 0.0, 50.0, 10_000.0):
        chart.add_point("cpu.utilization.total", value)
    chart.update()
    qtbot.wait(20)

    assert list(chart._series["cpu.utilization.total"]["values"]) == [
        -10_000.0,
        0.0,
        50.0,
        10_000.0,
    ]
    assert not chart.grab().isNull()

