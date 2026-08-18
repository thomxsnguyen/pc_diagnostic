from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pc_diagnostic.gui.bridge import TelemetryBridge

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class BaseView(QWidget):
    """Base class for all tabbed views in the PC Diagnostic GUI."""

    def __init__(self, bridge: TelemetryBridge, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
        self.bridge = bridge
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize view layout and widgets."""
        pass


class OverviewView(BaseView):
    """System Overview Dashboard View (Phase 2)."""

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header Title
        title = QLabel("System Overview Dashboard")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        # Overview Card Container
        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)

        subtitle = QLabel("Real-time telemetry and resource performance summary")
        subtitle.setProperty("class", "card_subtitle")
        card_layout.addWidget(subtitle)

        # Live Metric Preview Row
        preview_layout = QHBoxLayout()
        self.lbl_cpu = QLabel("CPU: Connecting...")
        self.lbl_cpu.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.lbl_ram = QLabel("RAM: Connecting...")
        self.lbl_ram.setStyleSheet("font-size: 16px; font-weight: 700;")
        preview_layout.addWidget(self.lbl_cpu)
        preview_layout.addWidget(self.lbl_ram)
        preview_layout.addStretch()

        card_layout.addLayout(preview_layout)
        layout.addWidget(card)
        layout.addStretch()

        # Connect bridge signal
        self.bridge.snapshot_updated.connect(self._on_snapshot)

    def _on_snapshot(self, snapshot: Any) -> None:
        if not PYSIDE6_AVAILABLE or snapshot is None:
            return
        for r in snapshot.readings:
            if r.metric == "cpu.utilization.total":
                self.lbl_cpu.setText(f"CPU Total: {r.value:.1f}%")
            elif r.metric == "memory.utilization":
                self.lbl_ram.setText(f"Memory: {r.value:.1f}%")


class SensorsView(BaseView):
    """Hardware Thermals & Sensors View (Phase 3)."""

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Hardware & Thermal Sensors")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(
            QLabel("Per-core CPU frequencies, temperatures, fan speeds, and voltage rails.")
        )
        layout.addWidget(card)
        layout.addStretch()


class ProcessesView(BaseView):
    """Process Inspector & Task Manager View (Phase 4)."""

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Process Inspector")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(
            QLabel("Interactive sortable process table with CPU, Memory, I/O inspection.")
        )
        layout.addWidget(card)
        layout.addStretch()


class AlertsView(BaseView):
    """Alerting & Incident Management View (Phase 4)."""

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Alerts & Incident Center")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(
            QLabel("Active incidents, threshold configuration, and historical notification log.")
        )
        layout.addWidget(card)
        layout.addStretch()


class DiagnosticsView(BaseView):
    """AI Diagnostics Studio View (Phase 5)."""

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("AI Diagnostics Studio")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(
            QLabel("On-demand CrewAI system diagnostics, evidence inspector, and markdown report generator.")
        )
        layout.addWidget(card)
        layout.addStretch()


class SettingsView(BaseView):
    """Settings & Telemetry Preferences View."""

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Application Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(
            QLabel("Theme customization, telemetry refresh interval, and hardware provider settings.")
        )
        layout.addWidget(card)
        layout.addStretch()
