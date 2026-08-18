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


from pc_diagnostic.gui.views.overview_view import OverviewView


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
