from __future__ import annotations

import copy
import html
import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pc_diagnostic.diagnostics.crew import run_diagnosis

if TYPE_CHECKING:
    from pc_diagnostic.alerts.models import Incident
    from pc_diagnostic.gui.bridge import TelemetryBridge
    from pc_diagnostic.models import MetricReading, Snapshot

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QGuiApplication, QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import (
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QSplitter,
        QTextBrowser,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QThread = object  # type: ignore[misc,assignment]
    QWidget = object  # type: ignore[misc,assignment]


def _format_bytes(value: float) -> str:
    size = max(0.0, float(value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def build_evidence_packet(
    snapshot: Snapshot, incidents: Iterable[Incident] = ()
) -> dict[str, Any]:
    """Build the immutable diagnostic input captured from one telemetry snapshot."""
    metrics: dict[str, list[MetricReading]] = {}
    for reading in snapshot.readings:
        metrics.setdefault(reading.metric, []).append(reading)

    def value(metric_names: tuple[str, ...], default: float) -> float:
        for name in metric_names:
            readings = metrics.get(name)
            if readings:
                return float(readings[0].value)
        return default

    cpu_model = "Unknown"
    for name in ("system.info.cpu_model", "cpu.model"):
        model_readings = metrics.get(name, [])
        if model_readings:
            cpu_model = model_readings[0].tags.get(
                "value", model_readings[0].tags.get("model", "Unknown")
            )
            break

    memory_by_pid = {
        (r.tags.get("pid", ""), r.tags.get("type", "")): r.value
        for r in metrics.get("process.memory.used", [])
    }
    cpu_by_pid = {
        (r.tags.get("pid", ""), r.tags.get("type", "")): r.value
        for r in metrics.get("process.cpu_percent", [])
    }

    top_cpu_procs: list[dict[str, Any]] = [
        {
            "pid": r.tags.get("pid", ""),
            "name": r.tags.get("name", "Unknown"),
            "cpu": float(r.value),
            "mem": float(memory_by_pid.get((r.tags.get("pid", ""), "cpu_top"), 0.0)),
        }
        for r in metrics.get("process.cpu_percent", [])
        if r.tags.get("type") == "cpu_top"
    ]
    top_cpu_procs.sort(key=lambda proc: proc["cpu"], reverse=True)

    top_mem_procs: list[dict[str, Any]] = [
        {
            "pid": r.tags.get("pid", ""),
            "name": r.tags.get("name", "Unknown"),
            "cpu": float(cpu_by_pid.get((r.tags.get("pid", ""), "mem_top"), 0.0)),
            "mem_str": _format_bytes(r.value),
        }
        for r in metrics.get("process.memory.used", [])
        if r.tags.get("type") == "mem_top"
    ]
    top_mem_procs.sort(
        key=lambda proc: memory_by_pid.get((str(proc["pid"]), "mem_top"), 0.0),
        reverse=True,
    )

    active_incidents = []
    for incident in incidents:
        state = getattr(incident.state, "value", str(incident.state))
        if state == "NORMAL":
            continue
        active_incidents.append(
            {
                "rule_id": incident.rule.id,
                "state": state,
                "value": float(incident.value),
            }
        )

    cpu_temp = value(
        (
            "system.temperature.cpu",
            "thermal.cpu_temp",
            "thermal.cpu.temp",
            "thermal.cpu.package_temp",
        ),
        -1.0,
    )
    gpu_temp = value(
        ("system.temperature.gpu", "thermal.gpu_temp", "thermal.gpu.temp"),
        -1.0,
    )

    return {
        "snapshot_timestamp": float(snapshot.timestamp),
        "cpu_model": cpu_model,
        "cpu_util": value(("cpu.utilization.total",), 0.0),
        "ram_util": value(("memory.utilization",), 0.0),
        "ram_used_str": _format_bytes(value(("memory.used", "memory.used_bytes"), 0.0)),
        "cpu_temp": cpu_temp,
        "gpu_temp": gpu_temp,
        "fan_speed": value(("system.fan.speed", "thermal.fan_speed"), -1.0),
        "thermal_throttling_risk": max(cpu_temp, gpu_temp) >= 80.0,
        "top_cpu_procs": top_cpu_procs,
        "top_mem_procs": top_mem_procs,
        "active_incidents": active_incidents,
    }


if PYSIDE6_AVAILABLE:

    class DiagnosticWorkerThread(QThread):
        """Run the potentially slow diagnostic engine away from the UI thread."""

        status_updated = Signal(str)
        progress_percent = Signal(int)
        diagnosis_finished = Signal(str)

        def __init__(
            self,
            evidence: dict[str, Any],
            parent: Any = None,
            diagnosis_runner: Callable[[dict[str, Any]], str] | None = None,
        ) -> None:
            super().__init__(parent)
            self.evidence = copy.deepcopy(evidence)
            self._diagnosis_runner = diagnosis_runner or run_diagnosis

        def run(self) -> None:
            self.status_updated.emit("Preparing captured evidence…")
            self.progress_percent.emit(10)
            try:
                self.status_updated.emit("Running diagnostic analysis…")
                self.progress_percent.emit(35)
                report = self._diagnosis_runner(self.evidence)
            except Exception as exc:
                logger.exception("Diagnostic worker failed")
                report = (
                    "# Diagnosis Error\n\n"
                    f"The diagnostic engine could not complete: `{exc}`"
                )
                self.status_updated.emit("Diagnosis failed")
            else:
                self.status_updated.emit("Diagnosis complete")
            self.progress_percent.emit(100)
            self.diagnosis_finished.emit(report)

else:

    class DiagnosticWorkerThread:  # type: ignore[no-redef]
        def __init__(self, evidence: dict[str, Any], parent: Any = None) -> None:
            raise RuntimeError("PySide6 is required for DiagnosticWorkerThread")


class DiagnosticsView(QWidget):
    """Asynchronous diagnosis runner, evidence inspector, and report exporter."""

    def __init__(
        self,
        bridge: TelemetryBridge,
        parent: Any = None,
        diagnosis_runner: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required for DiagnosticsView")
        super().__init__(parent)
        self.bridge = bridge
        self._diagnosis_runner = diagnosis_runner
        self._worker: DiagnosticWorkerThread | None = None
        self._evidence: dict[str, Any] = {}
        self._report_markdown = ""
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        header = QFrame(self)
        header.setProperty("class", "card")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        title_column = QVBoxLayout()
        title = QLabel("AI DIAGNOSTICS STUDIO")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.status_label = QLabel("Ready to analyze the latest telemetry snapshot")
        self.status_label.setStyleSheet("color: #90A4AE; font-size: 11px;")
        title_column.addWidget(title)
        title_column.addWidget(self.status_label)
        header_layout.addLayout(title_column, stretch=1)

        self.health_badge = QLabel("Health —")
        self.health_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.health_badge.setMinimumWidth(90)
        self._style_health_badge(None)
        header_layout.addWidget(self.health_badge)

        self.run_button = QPushButton("Run Full System Diagnosis")
        self.run_button.clicked.connect(self.start_diagnosis)
        header_layout.addWidget(self.run_button)
        layout.addWidget(header)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        evidence_card = QFrame(splitter)
        evidence_card.setProperty("class", "card")
        evidence_layout = QVBoxLayout(evidence_card)
        evidence_layout.addWidget(QLabel("CAPTURED EVIDENCE"))
        self.evidence_tree = QTreeWidget(evidence_card)
        self.evidence_tree.setHeaderLabels(["Evidence", "Captured value"])
        self.evidence_tree.setAlternatingRowColors(True)
        evidence_layout.addWidget(self.evidence_tree)

        report_card = QFrame(splitter)
        report_card.setProperty("class", "card")
        report_layout = QVBoxLayout(report_card)
        report_layout.addWidget(QLabel("DIAGNOSTIC REPORT"))
        self.recommendation_categories = QLabel(
            "Recommendation focus will appear after analysis"
        )
        self.recommendation_categories.setWordWrap(True)
        self.recommendation_categories.setStyleSheet("color: #90A4AE; font-size: 11px;")
        report_layout.addWidget(self.recommendation_categories)
        self.report_view = QTextBrowser(report_card)
        self.report_view.setOpenExternalLinks(True)
        self.report_view.setPlaceholderText(
            "Run a diagnosis to generate hardware and software recommendations."
        )
        report_layout.addWidget(self.report_view)

        splitter.addWidget(evidence_card)
        splitter.addWidget(report_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        actions = QHBoxLayout()
        actions.addStretch()
        self.save_markdown_button = QPushButton("Save Markdown")
        self.save_html_button = QPushButton("Export HTML")
        self.save_pdf_button = QPushButton("Export PDF")
        self.copy_button = QPushButton("Copy Report")
        self.save_markdown_button.clicked.connect(self.save_markdown)
        self.save_html_button.clicked.connect(self.save_html)
        self.save_pdf_button.clicked.connect(self.save_pdf)
        self.copy_button.clicked.connect(self.copy_report)
        for button in (
            self.save_markdown_button,
            self.save_html_button,
            self.save_pdf_button,
            self.copy_button,
        ):
            button.setEnabled(False)
            actions.addWidget(button)
        layout.addLayout(actions)

    def start_diagnosis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        snapshot = self.bridge.get_latest_snapshot()
        if snapshot is None:
            self.status_label.setText("No telemetry snapshot is available yet")
            return

        incidents = self.bridge.evaluator.incidents.values()
        self._evidence = build_evidence_packet(snapshot, incidents)
        self._populate_evidence_tree(self._evidence)
        self._report_markdown = ""
        self.report_view.clear()
        self._style_health_badge(None)
        self.run_button.setEnabled(False)
        self.progress_bar.setValue(0)

        worker = DiagnosticWorkerThread(
            self._evidence, self, diagnosis_runner=self._diagnosis_runner
        )
        self._worker = worker
        worker.status_updated.connect(self.status_label.setText)
        worker.progress_percent.connect(self.progress_bar.setValue)
        worker.diagnosis_finished.connect(self._on_diagnosis_finished)
        worker.finished.connect(self._on_worker_stopped)
        worker.start()

    def _on_diagnosis_finished(self, report: str) -> None:
        self._report_markdown = report
        self.report_view.setMarkdown(report)
        self._style_health_badge(self._calculate_health_score(self._evidence))
        hardware, software = self._categorise_recommendations(report)
        hardware_text = "\n".join(f"• {item}" for item in hardware) or "• None"
        software_text = "\n".join(f"• {item}" for item in software) or "• None"
        self.recommendation_categories.setText(
            f"Hardware fixes\n{hardware_text}\n\nSoftware fixes\n{software_text}"
        )
        for button in (
            self.save_markdown_button,
            self.save_html_button,
            self.save_pdf_button,
            self.copy_button,
        ):
            button.setEnabled(True)
        self.bridge.emit_diagnosis(report)

    def _on_worker_stopped(self) -> None:
        worker = self._worker
        self._worker = None
        self.run_button.setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    @staticmethod
    def _calculate_health_score(evidence: dict[str, Any]) -> int:
        score = 100.0
        cpu = float(evidence.get("cpu_util", 0.0))
        memory = float(evidence.get("ram_util", 0.0))
        hottest = max(
            float(evidence.get("cpu_temp", -1.0)),
            float(evidence.get("gpu_temp", -1.0)),
        )
        if cpu > 55.0:
            score -= min(30.0, (cpu - 55.0) * 0.75)
        if memory > 55.0:
            score -= min(30.0, (memory - 55.0) * 0.75)
        if hottest > 60.0:
            score -= min(30.0, (hottest - 60.0) * 1.2)
        score -= min(30.0, len(evidence.get("active_incidents", [])) * 10.0)
        return max(0, min(100, round(score)))

    @staticmethod
    def _categorise_recommendations(report: str) -> tuple[list[str], list[str]]:
        """Present generated recommendations under hardware/software headings."""
        sections = re.split(r"Actionable Recommendations", report, flags=re.I)
        text = sections[-1] if len(sections) > 1 else report
        recommendations = [
            match.strip() for match in re.findall(r"^\s*[-*]\s+(.+)$", text, flags=re.M)
        ]
        hardware_terms = (
            "airflow",
            "cooling",
            "dust",
            "fan",
            "hardware",
            "temperature",
            "thermal",
            "vent",
        )
        hardware = [
            item
            for item in recommendations
            if any(term in item.lower() for term in hardware_terms)
        ]
        software = [item for item in recommendations if item not in hardware]
        return hardware, software

    def _style_health_badge(self, score: int | None) -> None:
        if score is None:
            text, color = "Health —", "#607D8B"
        elif score >= 80:
            text, color = f"Health {score}%", "#00C853"
        elif score >= 55:
            text, color = f"Health {score}%", "#FFD600"
        else:
            text, color = f"Health {score}%", "#FF1744"
        self.health_badge.setText(text)
        self.health_badge.setStyleSheet(
            f"background-color: {color}; color: #FFFFFF; font-weight: 800; "
            "border-radius: 5px; padding: 7px 10px;"
        )

    def _populate_evidence_tree(self, evidence: dict[str, Any]) -> None:
        self.evidence_tree.clear()
        groups = {
            "System & CPU": ("snapshot_timestamp", "cpu_model", "cpu_util"),
            "Memory": ("ram_util", "ram_used_str"),
            "Thermals & Cooling": (
                "cpu_temp",
                "gpu_temp",
                "fan_speed",
                "thermal_throttling_risk",
            ),
            "Top CPU Processes": ("top_cpu_procs",),
            "Top Memory Processes": ("top_mem_procs",),
            "Active Incidents": ("active_incidents",),
        }
        for group_name, keys in groups.items():
            parent = QTreeWidgetItem([group_name, ""])
            self.evidence_tree.addTopLevelItem(parent)
            for key in keys:
                self._append_tree_value(parent, key, evidence.get(key))
            parent.setExpanded(True)
        self.evidence_tree.resizeColumnToContents(0)

    def _append_tree_value(
        self, parent: QTreeWidgetItem, label: str, value: Any
    ) -> None:
        if isinstance(value, dict):
            item = QTreeWidgetItem(parent, [label, ""])
            for child_label, child_value in value.items():
                self._append_tree_value(item, str(child_label), child_value)
            item.setExpanded(True)
        elif isinstance(value, list):
            item = QTreeWidgetItem(parent, [label, f"{len(value)} item(s)"])
            for index, child_value in enumerate(value, start=1):
                self._append_tree_value(item, str(index), child_value)
            item.setExpanded(True)
        else:
            QTreeWidgetItem(parent, [label.replace("_", " ").title(), str(value)])

    def _choose_path(self, caption: str, suffix: str, file_filter: str) -> str:
        path, _ = QFileDialog.getSaveFileName(
            self, caption, f"pc-diagnostic-report.{suffix}", file_filter
        )
        return path

    def save_markdown(self, path: str | None = None) -> bool:
        target = path or self._choose_path(
            "Save Diagnostic Report", "md", "Markdown (*.md)"
        )
        if not target or not self._report_markdown:
            return False
        Path(target).write_text(self._report_markdown, encoding="utf-8")
        self.status_label.setText(f"Markdown report saved to {target}")
        return True

    def _report_html(self) -> str:
        document = QTextDocument()
        document.setMarkdown(self._report_markdown)
        body = document.toHtml()
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>PC Diagnostic Report</title></head><body>"
            f"{body}<hr><p><small>Captured evidence: "
            f"{html.escape(str(self._evidence.get('snapshot_timestamp', 'unknown')))}"
            "</small></p></body></html>"
        )

    def save_html(self, path: str | None = None) -> bool:
        target = path or self._choose_path(
            "Export Diagnostic Report", "html", "HTML (*.html)"
        )
        if not target or not self._report_markdown:
            return False
        Path(target).write_text(self._report_html(), encoding="utf-8")
        self.status_label.setText(f"HTML report saved to {target}")
        return True

    def save_pdf(self, path: str | None = None) -> bool:
        target = path or self._choose_path(
            "Export Diagnostic Report", "pdf", "PDF (*.pdf)"
        )
        if not target or not self._report_markdown:
            return False
        writer = QPdfWriter(target)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setTitle("PC Diagnostic Report")
        document = QTextDocument()
        document.setMarkdown(self._report_markdown)
        document.print_(writer)
        self.status_label.setText(f"PDF report saved to {target}")
        return True

    def copy_report(self) -> bool:
        if not self._report_markdown:
            return False
        QGuiApplication.clipboard().setText(self._report_markdown)
        self.status_label.setText("Report copied to clipboard")
        return True
