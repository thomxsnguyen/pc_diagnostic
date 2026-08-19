from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pc_diagnostic.alerts.models import AlertRule, Incident, IncidentState
from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.views.diagnostics_view import (
    DiagnosticsView,
    DiagnosticWorkerThread,
    build_evidence_packet,
)
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot

pytestmark = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


def _snapshot() -> Snapshot:
    return Snapshot(
        timestamp=1234.5,
        readings=[
            MetricReading("cpu.utilization.total", 92.0, MetricUnit.PERCENT, "test"),
            MetricReading("memory.utilization", 78.0, MetricUnit.PERCENT, "test"),
            MetricReading("memory.used_bytes", 8 * 1024**3, MetricUnit.BYTES, "test"),
            MetricReading(
                "cpu.model",
                0.0,
                MetricUnit.INFO,
                "test",
                {"model": "Test CPU"},
            ),
            MetricReading("thermal.cpu.temp", 84.0, MetricUnit.CELSIUS, "test"),
            MetricReading(
                "process.cpu_percent",
                80.0,
                MetricUnit.PERCENT,
                "test",
                {"pid": "42", "name": "busy", "type": "cpu_top"},
            ),
            MetricReading(
                "process.memory.used",
                512 * 1024**2,
                MetricUnit.BYTES,
                "test",
                {"pid": "42", "name": "busy", "type": "cpu_top"},
            ),
        ],
    )


def test_build_evidence_packet_captures_required_groups() -> None:
    rule = AlertRule("high_cpu", "cpu", "gt", 90.0, 1.0, 5.0, 30.0)
    incident = Incident(rule, IncidentState.FIRING, value=92.0)

    evidence = build_evidence_packet(_snapshot(), [incident])

    assert evidence["snapshot_timestamp"] == 1234.5
    assert evidence["cpu_model"] == "Test CPU"
    assert evidence["ram_used_str"] == "8.0 GB"
    assert evidence["thermal_throttling_risk"] is True
    assert evidence["top_cpu_procs"][0]["pid"] == "42"
    assert evidence["active_incidents"][0]["rule_id"] == "high_cpu"


def test_worker_emits_progress_and_report(qtbot: Any) -> None:
    evidence = {"nested": [{"value": 1}]}

    def diagnose(packet: dict[str, list[dict[str, int]]]) -> str:
        return f"report {packet['nested'][0]['value']}"

    worker = DiagnosticWorkerThread(
        evidence,
        diagnosis_runner=diagnose,
    )
    progress: list[int] = []
    worker.progress_percent.connect(progress.append)

    with qtbot.waitSignal(worker.diagnosis_finished, timeout=2000) as signal:
        worker.start()

    worker.wait(2000)
    assert signal.args == ["report 1"]
    assert progress[0] == 10
    assert progress[-1] == 100


def test_worker_returns_markdown_error(qtbot: Any) -> None:
    def fail(_evidence: dict[str, object]) -> str:
        raise RuntimeError("offline")

    worker = DiagnosticWorkerThread({}, diagnosis_runner=fail)
    with qtbot.waitSignal(worker.diagnosis_finished, timeout=2000) as signal:
        worker.start()
    worker.wait(2000)

    assert "Diagnosis Error" in signal.args[0]
    assert "offline" in signal.args[0]


def test_view_runs_without_blocking_and_exports(qtbot: Any, tmp_path: Path) -> None:
    cache = RollingCache()
    cache.push(_snapshot())
    bridge = TelemetryBridge(cache)
    view = DiagnosticsView(
        bridge,
        diagnosis_runner=lambda _packet: (
            "# Report\n\n**Overall System Status**: WARNING\n\n"
            "## Actionable Recommendations\n- Clean dust from fans.\n"
            "- Close the busy process."
        ),
    )
    qtbot.addWidget(view)

    view.start_diagnosis()
    qtbot.waitUntil(lambda: view._worker is None, timeout=2000)

    markdown_path = tmp_path / "report.md"
    html_path = tmp_path / "report.html"
    assert view.save_markdown(str(markdown_path)) is True
    assert view.save_html(str(html_path)) is True
    assert "Overall System Status" in markdown_path.read_text()
    assert "<!doctype html>" in html_path.read_text()
    assert "Hardware fixes" in view.recommendation_categories.text()
    assert "Software fixes" in view.recommendation_categories.text()
    assert view.progress_bar.value() == 100
    assert view.copy_report() is True

    from PySide6.QtGui import QGuiApplication

    assert "Overall System Status" in QGuiApplication.clipboard().text()
