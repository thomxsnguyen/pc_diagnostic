from __future__ import annotations

import copy
import html
import logging
import re
from collections.abc import Callable, Iterable
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pc_diagnostic.credentials import AIProvider
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
        QHeaderView,
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
        self._provider: AIProvider | None = None
        self._worker: DiagnosticWorkerThread | None = None
        self._evidence: dict[str, Any] = {}
        self._report_markdown = ""
        self._init_ui()

    @property
    def provider(self) -> AIProvider | None:
        return self._provider

    def set_provider(self, provider: AIProvider) -> None:
        """Select the provider identifier without passing credential data."""
        self._provider = provider

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        header = QFrame(self)
        header.setProperty("class", "card")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(16)

        self.status_label = QLabel("Ready to analyze the latest telemetry snapshot")
        self.status_label.setObjectName("studio_page_subtitle")
        header_layout.addWidget(self.status_label, stretch=1)

        self.health_badge = QLabel("Health —")
        self.health_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.health_badge.setMinimumWidth(96)
        self._style_health_badge(None)
        header_layout.addWidget(self.health_badge)

        self.run_button = QPushButton("Run diagnosis")
        self.run_button.setProperty("class", "primary_btn")
        self.run_button.setMinimumWidth(138)
        self.run_button.clicked.connect(self.start_diagnosis)
        header_layout.addWidget(self.run_button)
        layout.addWidget(header)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("studio_progress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(5)
        layout.addWidget(self.progress_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        evidence_card = QFrame(splitter)
        evidence_card.setProperty("class", "card")
        evidence_layout = QVBoxLayout(evidence_card)
        evidence_layout.setContentsMargins(14, 14, 14, 14)
        evidence_layout.setSpacing(10)

        evidence_title = QLabel("Evidence snapshot")
        evidence_title.setObjectName("studio_section_title")
        evidence_subtitle = QLabel("Telemetry captured for this analysis")
        evidence_subtitle.setObjectName("studio_section_subtitle")
        evidence_layout.addWidget(evidence_title)
        evidence_layout.addWidget(evidence_subtitle)

        self.evidence_tree = QTreeWidget(evidence_card)
        self.evidence_tree.setObjectName("evidence_tree")
        self.evidence_tree.setHeaderLabels(["Evidence", "Captured value"])
        self.evidence_tree.setAlternatingRowColors(False)
        self.evidence_tree.setIndentation(16)
        self.evidence_tree.setUniformRowHeights(True)
        evidence_header = self.evidence_tree.header()
        evidence_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        evidence_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        evidence_header.resizeSection(0, 190)
        evidence_layout.addWidget(self.evidence_tree)

        report_card = QFrame(splitter)
        report_card.setProperty("class", "card")
        report_layout = QVBoxLayout(report_card)
        report_layout.setContentsMargins(14, 14, 14, 14)
        report_layout.setSpacing(10)

        report_header = QHBoxLayout()
        report_header.setSpacing(6)
        report_title_column = QVBoxLayout()
        report_title_column.setSpacing(2)
        report_title = QLabel("Diagnostic report")
        report_title.setObjectName("studio_section_title")
        report_subtitle = QLabel("Analysis, findings, and recommended actions")
        report_subtitle.setObjectName("studio_section_subtitle")
        report_title_column.addWidget(report_title)
        report_title_column.addWidget(report_subtitle)
        report_header.addLayout(report_title_column, stretch=1)

        self.copy_button = QPushButton("Copy")
        self.save_markdown_button = QPushButton("Markdown")
        self.save_html_button = QPushButton("HTML")
        self.save_pdf_button = QPushButton("PDF")
        self.save_markdown_button.clicked.connect(self.save_markdown)
        self.save_html_button.clicked.connect(self.save_html)
        self.save_pdf_button.clicked.connect(self.save_pdf)
        self.copy_button.clicked.connect(self.copy_report)
        for button in (
            self.copy_button,
            self.save_markdown_button,
            self.save_html_button,
            self.save_pdf_button,
        ):
            button.setProperty("class", "secondary_btn")
            button.setEnabled(False)
            report_header.addWidget(button)
        report_layout.addLayout(report_header)

        self.report_view = QTextBrowser(report_card)
        self.report_view.setObjectName("report_view")
        self.report_view.setOpenExternalLinks(True)
        self.report_view.document().setDocumentMargin(14.0)
        self.report_view.document().setDefaultStyleSheet(
            "h1 { font-size: 22px; font-weight: 700; margin: 0 0 14px 0; }"
            "h2 { font-size: 16px; font-weight: 700; margin: 20px 0 8px 0; }"
            "h3 { font-size: 13px; font-weight: 700; margin: 16px 0 6px 0; }"
            "p { margin: 0 0 10px 0; line-height: 1.35; }"
            "ul, ol { margin: 4px 0 14px 22px; }"
            "li { margin-bottom: 6px; }"
        )
        self.report_view.setPlaceholderText(
            "Run a diagnosis to generate hardware and software recommendations."
        )
        report_layout.addWidget(self.report_view, stretch=1)

        recommendation_panel = QFrame(report_card)
        recommendation_panel.setObjectName("recommendation_panel")
        recommendation_layout = QVBoxLayout(recommendation_panel)
        recommendation_layout.setContentsMargins(12, 10, 12, 10)
        recommendation_layout.setSpacing(4)
        recommendation_title = QLabel("Recommendation summary")
        recommendation_title.setObjectName("studio_summary_title")
        self.recommendation_categories = QLabel(
            "Recommendation focus will appear after analysis"
        )
        self.recommendation_categories.setWordWrap(True)
        self.recommendation_categories.setObjectName("recommendation_categories")
        recommendation_layout.addWidget(recommendation_title)
        recommendation_layout.addWidget(self.recommendation_categories)
        report_layout.addWidget(recommendation_panel)

        splitter.addWidget(evidence_card)
        splitter.addWidget(report_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([360, 760])
        layout.addWidget(splitter, stretch=1)

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

        diagnosis_runner = self._diagnosis_runner
        if diagnosis_runner is None and self._provider is not None:
            diagnosis_runner = partial(run_diagnosis, provider=self._provider)
        worker = DiagnosticWorkerThread(
            self._evidence, self, diagnosis_runner=diagnosis_runner
        )
        self._worker = worker
        worker.status_updated.connect(self.status_label.setText)
        worker.progress_percent.connect(self.progress_bar.setValue)
        worker.diagnosis_finished.connect(self._on_diagnosis_finished)
        worker.finished.connect(self._on_worker_stopped)
        worker.start()

    def _on_diagnosis_finished(self, report: str) -> None:
        self._report_markdown = report
        self.report_view.setMarkdown(self._format_report_for_display(report))
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

    @staticmethod
    def _format_report_for_display(report: str) -> str:
        """Add visual separation without altering saved or copied report content."""
        normalized = report.strip()
        return re.sub(r"(?m)^##\s+", "\n\n---\n\n## ", normalized)

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
            text, color = "Health —", "#6F7680"
        elif score >= 80:
            text, color = f"Health {score}%", "#00C853"
        elif score >= 55:
            text, color = f"Health {score}%", "#FFD600"
        else:
            text, color = f"Health {score}%", "#FF1744"
        self.health_badge.setText(text)
        self.health_badge.setStyleSheet(
            f"background-color: transparent; color: {color}; font-weight: 700; "
            "border: 1px solid #30343B; border-radius: 4px; padding: 7px 10px;"
        )

    def _populate_evidence_tree(self, evidence: dict[str, Any]) -> None:
        """Display diagnostic evidence with readable labels, units, and hierarchy."""
        self.evidence_tree.clear()
        groups = (
            (
                "System & CPU",
                (
                    (
                        "Captured",
                        self._format_timestamp(evidence.get("snapshot_timestamp")),
                    ),
                    ("Processor", str(evidence.get("cpu_model", "Unknown"))),
                    ("CPU utilization", self._format_percent(evidence.get("cpu_util"))),
                ),
            ),
            (
                "Memory",
                (
                    (
                        "Memory utilization",
                        self._format_percent(evidence.get("ram_util")),
                    ),
                    ("Memory used", str(evidence.get("ram_used_str", "Unavailable"))),
                ),
            ),
            (
                "Thermals & Cooling",
                tuple(self._thermal_evidence_rows(evidence)),
            ),
        )
        for group_name, rows in groups:
            parent = QTreeWidgetItem([group_name, ""])
            self.evidence_tree.addTopLevelItem(parent)
            for label, value in rows:
                QTreeWidgetItem(parent, [label, value])
            parent.setExpanded(True)

        self._append_process_group(
            "Top CPU Processes", evidence.get("top_cpu_procs", []), primary="cpu"
        )
        self._append_process_group(
            "Top Memory Processes", evidence.get("top_mem_procs", []), primary="memory"
        )
        self._append_incident_group(evidence.get("active_incidents", []))

    @staticmethod
    def _format_percent(value: Any) -> str:
        try:
            return f"{float(value):.1f}%"
        except (TypeError, ValueError):
            return "Unavailable"

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        try:
            timestamp = datetime.fromtimestamp(float(value)).astimezone()
        except (OSError, OverflowError, TypeError, ValueError):
            return "Unavailable"
        return timestamp.strftime("%b %d · %I:%M %p")

    @staticmethod
    def _thermal_evidence_rows(
        evidence: dict[str, Any],
    ) -> Iterable[tuple[str, str]]:
        for key, label, unit in (
            ("cpu_temp", "CPU temperature", "°C"),
            ("gpu_temp", "GPU temperature", "°C"),
            ("fan_speed", "Fan speed", "RPM"),
        ):
            try:
                value = float(evidence.get(key, -1.0))
            except (TypeError, ValueError):
                continue
            if value >= 0.0:
                yield label, f"{value:.1f} {unit}"
        yield (
            "Thermal throttling risk",
            "Detected" if evidence.get("thermal_throttling_risk") else "Not detected",
        )

    def _append_process_group(
        self, title: str, processes: Any, *, primary: str
    ) -> None:
        process_list = processes if isinstance(processes, list) else []
        parent = QTreeWidgetItem([title, f"{len(process_list)} captured"])
        self.evidence_tree.addTopLevelItem(parent)
        for index, process in enumerate(process_list, start=1):
            if not isinstance(process, dict):
                continue
            name = str(process.get("name", "Unknown"))
            pid = str(process.get("pid", "—"))
            cpu = self._format_percent(process.get("cpu", 0.0))
            memory = process.get("mem_str")
            if memory is None:
                try:
                    memory = _format_bytes(float(process.get("mem", 0.0)))
                except (TypeError, ValueError):
                    memory = "Unavailable"
            detail = (
                f"{cpu} CPU · {memory} · PID {pid}"
                if primary == "cpu"
                else f"{memory} · {cpu} CPU · PID {pid}"
            )
            item = QTreeWidgetItem(parent, [f"{index}. {name}", detail])
            item.setToolTip(0, name)
            item.setToolTip(1, detail)
        parent.setExpanded(bool(process_list))

    def _append_incident_group(self, incidents: Any) -> None:
        incident_list = incidents if isinstance(incidents, list) else []
        parent = QTreeWidgetItem(
            ["Active Incidents", f"{len(incident_list)} active"]
        )
        self.evidence_tree.addTopLevelItem(parent)
        for incident in incident_list:
            if not isinstance(incident, dict):
                continue
            rule_id = str(incident.get("rule_id", "Unknown rule"))
            state = str(incident.get("state", "Unknown")).title()
            value = incident.get("value")
            detail = state
            if isinstance(value, int | float):
                detail = f"{state} · Trigger value {value:.1f}"
            item = QTreeWidgetItem(
                parent, [rule_id.replace("_", " ").title(), detail]
            )
            item.setToolTip(1, detail)
        parent.setExpanded(bool(incident_list))

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
