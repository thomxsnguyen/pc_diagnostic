from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.theme import ThemeManager, ThemeMode
from pc_diagnostic.gui.tray import TrayManager
from pc_diagnostic.gui.views import (
    AlertsView,
    DiagnosticsView,
    OverviewView,
    ProcessesView,
    SensorsView,
    SettingsView,
)

if TYPE_CHECKING:
    from pc_diagnostic.alerts.dispatcher import AlertDispatcher
    from pc_diagnostic.cache import RollingCache
    from pc_diagnostic.models import CacheHealth

logger = logging.getLogger(__name__)

if PYSIDE6_AVAILABLE:
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
else:
    QMainWindow = object  # type: ignore[misc,assignment]


class MainWindow(QMainWindow):
    """Main desktop application window for PC Diagnostic."""

    def __init__(
        self,
        bridge: TelemetryBridge,
        theme_manager: ThemeManager | None = None,
        parent: Any = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError(
                "PySide6 is not available. Please install PySide6 "
                "to run the desktop GUI."
            )
        super().__init__(parent)
        self.bridge = bridge
        self.theme_manager = theme_manager or ThemeManager()

        self.setWindowTitle("PC Diagnostic — Telemetry & AI Diagnostic Monitor")
        self.resize(1120, 740)
        self.setMinimumSize(920, 600)

        self._init_ui()
        self._connect_signals()
        self.tray_manager = TrayManager(self, self.bridge)

        # Apply initial theme stylesheet
        self.setStyleSheet(self.theme_manager.get_stylesheet())

    def _init_ui(self) -> None:
        """Construct the main window layout: Header + Sidebar + Content Stack."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Header Bar
        header = self._build_header()
        root_layout.addWidget(header)

        # 2. Main Body (Sidebar + View Stack)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        body_layout.addWidget(sidebar)

        # 3. Stacked View Container
        self.stack = QStackedWidget(self)
        self.overview_view = OverviewView(self.bridge)
        self.sensors_view = SensorsView(self.bridge)
        self.processes_view = ProcessesView(self.bridge)
        self.alerts_view = AlertsView(self.bridge)
        self.diagnostics_view = DiagnosticsView(self.bridge)
        self.settings_view = SettingsView(self.bridge)

        self.stack.addWidget(self.overview_view)  # Index 0
        self.stack.addWidget(self.sensors_view)  # Index 1
        self.stack.addWidget(self.processes_view)  # Index 2
        self.stack.addWidget(self.alerts_view)  # Index 3
        self.stack.addWidget(self.diagnostics_view)  # Index 4
        self.stack.addWidget(self.settings_view)  # Index 5

        body_layout.addWidget(self.stack, stretch=1)
        root_layout.addLayout(body_layout, stretch=1)

    def _build_header(self) -> QWidget:
        """Create the top status and navigation header bar."""
        header_widget = QWidget(self)
        header_widget.setObjectName("top_header")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(12)

        # Title & Version Badge
        title_label = QLabel("⚡ PC DIAGNOSTIC")
        title_label.setObjectName("app_title")
        header_layout.addWidget(title_label)

        version_badge = QLabel("v0.2.0")
        version_badge.setObjectName("app_version_badge")
        header_layout.addWidget(version_badge)

        header_layout.addStretch()

        # Collector Status Indicator Badge
        self.status_badge = QLabel("● ACTIVE")
        self.status_badge.setProperty("class", "status_active")
        header_layout.addWidget(self.status_badge)

        # Cache Health Fill Indicator
        self.cache_badge = QLabel("Cache: 0/300")
        self.cache_badge.setStyleSheet(
            "font-size: 11px; font-weight: 600; padding: 2px 8px;"
        )
        header_layout.addWidget(self.cache_badge)

        # Active Alerts Badge
        self.alert_badge = QLabel("🚨 0 Alerts")
        self.alert_badge.setProperty("class", "alert_badge")
        header_layout.addWidget(self.alert_badge)

        # Theme Switcher Selector
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Cyberpunk Dark", ThemeMode.CYBERPUNK_DARK)
        self.theme_combo.addItem("OLED Stealth", ThemeMode.OLED_STEALTH)
        self.theme_combo.addItem("Clean Light", ThemeMode.CLEAN_LIGHT)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        header_layout.addWidget(self.theme_combo)

        return header_widget

    def _build_sidebar(self) -> QWidget:
        """Create the sidebar containing navigation buttons."""
        sidebar_widget = QWidget(self)
        sidebar_widget.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("📊  Overview", 0),
            ("🌡️  Sensors", 1),
            ("📋  Processes", 2),
            ("🚨  Alerts", 3),
            ("🤖  AI Studio", 4),
            ("⚙️  Settings", 5),
        ]

        self.nav_buttons: list[QPushButton] = []
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "nav_button")
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, index=idx: self._switch_view(index))
            self.nav_group.addButton(btn, idx)
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()
        return sidebar_widget

    def _connect_signals(self) -> None:
        """Connect TelemetryBridge signals to header indicators."""
        self.bridge.collector_status_changed.connect(self._on_collector_status)
        self.bridge.cache_health_changed.connect(self._on_cache_health)
        self.bridge.active_alerts_count_changed.connect(self._on_alerts_count)

    def _switch_view(self, index: int) -> None:
        """Switch active stacked view."""
        self.stack.setCurrentIndex(index)

    def _on_alerts_count(self, count: int) -> None:
        """Update active alerts count indicator badge."""
        if count > 0:
            self.alert_badge.setText(
                f"🚨 {count} Active Alert{'s' if count > 1 else ''}"
            )
            self.alert_badge.setStyleSheet(
                "background-color: #FF1744; color: #FFFFFF; font-weight: 700; "
                "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
            )
        else:
            self.alert_badge.setText("🚨 0 Alerts")
            self.alert_badge.setStyleSheet(
                "background-color: #1C2536; color: #90A4AE; font-weight: 600; "
                "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
            )

    def _on_collector_status(self, is_healthy: bool) -> None:
        """Update the header collector status badge."""
        if is_healthy:
            self.status_badge.setText("● ACTIVE")
            self.status_badge.setProperty("class", "status_active")
        else:
            self.status_badge.setText("▲ STALE")
            self.status_badge.setProperty("class", "status_stale")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _on_cache_health(self, health: CacheHealth) -> None:
        """Update cache capacity and fill metrics in header."""
        self.cache_badge.setText(f"Cache: {health.size}/{health.max_size}")

    def _on_theme_changed(self, index: int) -> None:
        """Apply newly selected theme stylesheet."""
        mode: ThemeMode = self.theme_combo.currentData()
        stylesheet = self.theme_manager.set_theme(mode)
        self.setStyleSheet(stylesheet)


def run_gui(
    cache: RollingCache,
    dispatcher: AlertDispatcher | None = None,
    refresh_rate: float = 1.0,
    theme_mode: ThemeMode = ThemeMode.CYBERPUNK_DARK,
) -> int:
    """Launch the PC Diagnostic Qt Desktop Application."""
    if not PYSIDE6_AVAILABLE:
        logger.error("PySide6 is not installed. Cannot start GUI.")
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("PC Diagnostic")

    theme_manager = ThemeManager(theme_mode)
    bridge = TelemetryBridge(cache, dispatcher)
    window = MainWindow(bridge, theme_manager)

    bridge.start(interval_ms=max(100, int(refresh_rate * 1000)))
    tray_started = window.tray_manager.start()
    app.setQuitOnLastWindowClosed(not tray_started)
    window.show()

    try:
        return app.exec()
    finally:
        bridge.stop()
