from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.views.diagnostics_view import (
    DiagnosticsView,
    DiagnosticWorkerThread,
    build_evidence_packet,
)
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


def _snapshot() -> Snapshot:
    return Snapshot(
        timestamp=1234.5,
        readings=[
            MetricReading(
                "system.info.cpu_model",
                0.0,
                MetricUnit.INFO,
                "test",
                {"value": "Test CPU"},
            ),
            MetricReading(
                "cpu.utilization.total", 91.0, MetricUnit.PERCENT, "test"
            ),
            MetricReading("memory.utilization", 62.0, MetricUnit.PERCENT, "test"),
            MetricReading("memory.used", 8 * 1024**3, MetricUnit.BYTES, "test"),
            MetricReading(
                "system.temperature.cpu", 76.0, MetricUnit.CELSIUS, "test"
            ),
            MetricReading("system.fan.speed", 1800.0, MetricUnit.RPM, "test"),
            MetricReading(
                "process.cpu_percent",
                42.0,
                MetricUnit.PERCENT,
                "test",
                {"pid": "7", "name": "worker", "type": "cpu_top"},
            ),
            MetricReading(
                "process.memory.used",
                512 * 1024**2,
                MetricUnit.BYTES,
                "test",
                {"pid": "7", "name": "worker", "type": "cpu_top"},
            ),
        ],
    )


def test_build_evidence_packet_uses_current_sensor_metrics() -> None:
    evidence = build_evidence_packet(_snapshot())

    assert evidence["snapshot_timestamp"] == 1234.5
    assert evidence["cpu_model"] == "Test CPU"
    assert evidence["cpu_util"] == 91.0
    assert evidence["ram_used_str"] == "8.0 GB"
    assert evidence["cpu_temp"] == 76.0
    assert evidence["fan_speed"] == 1800.0
    assert evidence["top_cpu_procs"][0] == {
        "pid": "7",
        "name": "worker",
        "cpu": 42.0,
        "mem": 512 * 1024**2,
    }


@pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 is unavailable")
def test_worker_emits_report_without_blocking(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "pc_diagnostic.gui.views.diagnostics_view.run_diagnosis",
        lambda evidence: f"# Result\n\nCPU: {evidence['cpu_util']}",
    )
    worker = DiagnosticWorkerThread({"cpu_util": 12.0})
    reports: list[str] = []
    progress: list[int] = []
    worker.diagnosis_finished.connect(reports.append)
    worker.progress_percent.connect(progress.append)

    with qtbot.waitSignal(worker.finished, timeout=2000):
        worker.start()

    assert reports == ["# Result\n\nCPU: 12.0"]
    assert progress[-1] == 100


@pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 is unavailable")
def test_report_exports(qtbot: Any, tmp_path: Path) -> None:
    cache = RollingCache()
    cache.push(_snapshot())
    view = DiagnosticsView(TelemetryBridge(cache))
    qtbot.addWidget(view)
    view._evidence = build_evidence_packet(_snapshot())
    view._on_diagnosis_finished("# Report\n\n- **Software:** stop a runaway task")

    markdown_path = tmp_path / "report.md"
    html_path = tmp_path / "report.html"
    pdf_path = tmp_path / "report.pdf"

    assert view.save_markdown(str(markdown_path))
    assert view.save_html(str(html_path))
    assert view.save_pdf(str(pdf_path))
    assert markdown_path.read_text(encoding="utf-8").startswith("# Report")
    assert "<!doctype html>" in html_path.read_text(encoding="utf-8")
    assert pdf_path.read_bytes().startswith(b"%PDF")


@pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 is unavailable")
def test_selected_provider_is_passed_to_default_diagnosis_runner(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pc_diagnostic.credentials import AIProvider

    captured: list[AIProvider] = []

    def diagnose(_evidence: dict[str, object], provider: AIProvider) -> str:
        captured.append(provider)
        return "# Provider report"

    monkeypatch.setattr(
        "pc_diagnostic.gui.views.diagnostics_view.run_diagnosis", diagnose
    )
    cache = RollingCache()
    cache.push(_snapshot())
    view = DiagnosticsView(TelemetryBridge(cache))
    view.set_provider(AIProvider.GEMINI)
    qtbot.addWidget(view)

    view.start_diagnosis()
    qtbot.waitUntil(lambda: view._worker is None, timeout=2000)

    assert captured == [AIProvider.GEMINI]
