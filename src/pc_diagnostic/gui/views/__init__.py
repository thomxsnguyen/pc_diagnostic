from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pc_diagnostic.gui.views.alerts_view import AlertsView
from pc_diagnostic.gui.views.overview_view import OverviewView
from pc_diagnostic.gui.views.processes_view import ProcessesView
from pc_diagnostic.gui.views.sensors_view import SensorsView

if TYPE_CHECKING:
    from pc_diagnostic.gui.bridge import TelemetryBridge

try:
    from PySide6.QtWidgets import (
        QFrame,
        QLabel,
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
            QLabel(
                "On-demand CrewAI system diagnostics, "
                "evidence inspector, and report generator."
            )
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
            QLabel("Theme customization, refresh interval, and hardware settings.")
        )
        layout.addWidget(card)
        layout.addStretch()


__all__ = [
    "AlertsView",
    "BaseView",
    "DiagnosticsView",
    "OverviewView",
    "ProcessesView",
    "SensorsView",
    "SettingsView",
]
