from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pc_diagnostic.alerts.models import Incident
    from pc_diagnostic.gui.app import MainWindow
    from pc_diagnostic.gui.bridge import TelemetryBridge
    from pc_diagnostic.models import Snapshot

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QEvent, QObject, QPoint, Qt
    from PySide6.QtGui import QAction, QColor, QIcon, QMouseEvent, QPainter, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QGridLayout,
        QLabel,
        QMenu,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QObject = object  # type: ignore[misc,assignment]
    QWidget = object  # type: ignore[misc,assignment]


if PYSIDE6_AVAILABLE:

    class MiniHud(QWidget):
        """Small always-on-top telemetry overlay that can be dragged anywhere."""

        def __init__(self, bridge: TelemetryBridge, parent: Any = None) -> None:
            super().__init__(parent)
            self.bridge = bridge
            self._drag_offset: QPoint | None = None
            self.setWindowTitle("PC Diagnostic Mini HUD")
            self.setWindowFlags(
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(250, 142)
            self._init_ui()
            self.bridge.snapshot_updated.connect(self.update_snapshot)

        def _init_ui(self) -> None:
            self.setStyleSheet(
                "QWidget#mini_hud { background-color: rgba(10, 15, 24, 225); "
                "border: 1px solid #253248; border-radius: 10px; } "
                "QLabel { color: #F0F6FC; font-size: 11px; }"
            )
            self.setObjectName("mini_hud")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 10, 14, 10)
            layout.setSpacing(6)

            title = QLabel("⚡ PC DIAGNOSTIC")
            title.setStyleSheet("font-size: 11px; font-weight: 800; color: #00E5FF;")
            layout.addWidget(title)

            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            grid.setVerticalSpacing(5)
            self.cpu_label = QLabel("CPU  —")
            self.ram_label = QLabel("RAM  —")
            self.gpu_label = QLabel("GPU  —")
            self.temp_label = QLabel("TEMP —")
            grid.addWidget(self.cpu_label, 0, 0)
            grid.addWidget(self.ram_label, 0, 1)
            grid.addWidget(self.gpu_label, 1, 0)
            grid.addWidget(self.temp_label, 1, 1)
            layout.addLayout(grid)

            self.process_label = QLabel("Top process: —")
            self.process_label.setStyleSheet("color: #90A4AE; font-size: 10px;")
            self.process_label.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(self.process_label)

        @staticmethod
        def _metric(snapshot: Snapshot, names: tuple[str, ...]) -> float | None:
            for reading in snapshot.readings:
                if reading.metric in names:
                    return float(reading.value)
            return None

        def update_snapshot(self, snapshot: Snapshot) -> None:
            cpu = self._metric(snapshot, ("cpu.utilization.total",))
            ram = self._metric(snapshot, ("memory.utilization",))
            gpu = self._metric(
                snapshot, ("gpu.utilization.total", "gpu.utilization")
            )
            temp = self._metric(
                snapshot,
                (
                    "system.temperature.cpu",
                    "thermal.cpu_temp",
                    "thermal.cpu.temp",
                    "thermal.cpu.package_temp",
                ),
            )
            self.cpu_label.setText(
                f"CPU  {cpu:.0f}%" if cpu is not None else "CPU  N/A"
            )
            self.ram_label.setText(
                f"RAM  {ram:.0f}%" if ram is not None else "RAM  N/A"
            )
            self.gpu_label.setText(
                f"GPU  {gpu:.0f}%" if gpu is not None else "GPU  N/A"
            )
            self.temp_label.setText(
                f"TEMP {temp:.0f}°C" if temp is not None else "TEMP N/A"
            )

            processes = [
                reading
                for reading in snapshot.readings
                if reading.metric == "process.cpu_percent"
                and reading.tags.get("type") == "cpu_top"
            ]
            if processes:
                top = max(processes, key=lambda reading: reading.value)
                name = top.tags.get("name", "Unknown")
                self.process_label.setText(
                    f"Top process: {name} ({float(top.value):.1f}% CPU)"
                )
            else:
                self.process_label.setText("Top process: N/A")

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if (
                self._drag_offset is not None
                and event.buttons() & Qt.MouseButton.LeftButton
            ):
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            self._drag_offset = None
            super().mouseReleaseEvent(event)


    class TrayManager(QObject):
        """Own the system tray icon, its actions, notifications, and mini HUD."""

        def __init__(
            self,
            main_window: MainWindow,
            bridge: TelemetryBridge,
            parent: Any = None,
        ) -> None:
            super().__init__(parent or main_window)
            self.main_window = main_window
            self.bridge = bridge
            self._quitting = False
            self._last_cpu: float | None = None
            self._last_temp: float | None = None
            self.mini_hud = MiniHud(bridge)

            self.tray_icon = QSystemTrayIcon(self._render_icon("—"), self)
            self.tray_icon.setToolTip("PC Diagnostic — waiting for telemetry")
            self.menu = QMenu(main_window)
            self.open_action = QAction("Open Dashboard", self)
            self.hud_action = QAction("Toggle Mini HUD", self)
            self.diagnose_action = QAction("Run AI Diagnosis", self)
            self.quit_action = QAction("Quit", self)
            self.menu.addAction(self.open_action)
            self.menu.addAction(self.hud_action)
            self.menu.addAction(self.diagnose_action)
            self.menu.addSeparator()
            self.menu.addAction(self.quit_action)
            self.tray_icon.setContextMenu(self.menu)

            self.open_action.triggered.connect(self.open_dashboard)
            self.hud_action.triggered.connect(self.toggle_mini_hud)
            self.diagnose_action.triggered.connect(self.run_diagnosis)
            self.quit_action.triggered.connect(self.quit_application)
            self.tray_icon.activated.connect(self._on_activated)
            self.bridge.snapshot_updated.connect(self._on_snapshot)
            self.bridge.alert_triggered.connect(self._on_alert)

        @staticmethod
        def is_available() -> bool:
            return QSystemTrayIcon.isSystemTrayAvailable()

        def start(self) -> bool:
            if not self.is_available():
                logger.info("No system tray is available; tray mode is disabled")
                return False
            self.main_window.installEventFilter(self)
            self.tray_icon.show()
            return True

        def eventFilter(  # noqa: N802
            self, watched: QObject, event: QEvent
        ) -> bool:
            if (
                watched is self.main_window
                and event.type() == QEvent.Type.Close
                and not self._quitting
                and self.tray_icon.isVisible()
            ):
                self.main_window.hide()
                self.tray_icon.showMessage(
                    "PC Diagnostic",
                    "Monitoring continues in the system tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500,
                )
                return True
            return super().eventFilter(watched, event)

        def open_dashboard(self) -> None:
            self.main_window.showNormal()
            self.main_window.raise_()
            self.main_window.activateWindow()

        def toggle_mini_hud(self) -> None:
            if self.mini_hud.isVisible():
                self.mini_hud.hide()
            else:
                snapshot = self.bridge.get_latest_snapshot()
                if snapshot is not None:
                    self.mini_hud.update_snapshot(snapshot)
                self.mini_hud.show()

        def run_diagnosis(self) -> None:
            self.open_dashboard()
            self.main_window._switch_view(4)
            self.main_window.nav_buttons[4].setChecked(True)
            self.main_window.diagnostics_view.start_diagnosis()

        def quit_application(self) -> None:
            self._quitting = True
            self.mini_hud.close()
            self.tray_icon.hide()
            self.main_window.close()
            app = QApplication.instance()
            if app is not None:
                app.quit()

        def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
            if reason in (
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick,
            ):
                self.open_dashboard()

        def _on_snapshot(self, snapshot: Snapshot) -> None:
            self._last_cpu = MiniHud._metric(snapshot, ("cpu.utilization.total",))
            self._last_temp = MiniHud._metric(
                snapshot,
                (
                    "system.temperature.cpu",
                    "thermal.cpu_temp",
                    "thermal.cpu.temp",
                    "thermal.cpu.package_temp",
                ),
            )
            if self._last_temp is not None:
                badge = f"{self._last_temp:.0f}°"
            elif self._last_cpu is not None:
                badge = f"{self._last_cpu:.0f}"
            else:
                badge = "—"
            self.tray_icon.setIcon(self._render_icon(badge))
            cpu_text = (
                f"CPU {self._last_cpu:.0f}%"
                if self._last_cpu is not None
                else "CPU N/A"
            )
            temp_text = (
                f"Temp {self._last_temp:.0f}°C"
                if self._last_temp is not None
                else "Temp N/A"
            )
            self.tray_icon.setToolTip(f"PC Diagnostic — {cpu_text} • {temp_text}")

        def _on_alert(self, incident: Incident) -> None:
            state = getattr(incident.state, "value", str(incident.state))
            if state != "FIRING" or not self.tray_icon.isVisible():
                return
            rule = incident.rule
            self.tray_icon.showMessage(
                "PC Diagnostic Alert",
                f"{rule.id}: {incident.value:.1f} (limit {rule.threshold:.1f})",
                QSystemTrayIcon.MessageIcon.Critical,
                5000,
            )

        @staticmethod
        def _render_icon(text: str) -> QIcon:
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#101826"))
            painter.setPen(QColor("#00E5FF"))
            painter.drawRoundedRect(2, 2, 60, 60, 13, 13)
            font = painter.font()
            font.setBold(True)
            font.setPixelSize(19 if len(text) <= 3 else 15)
            painter.setFont(font)
            painter.setPen(QColor("#F0F6FC"))
            painter.drawText(
                pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text[:4]
            )
            painter.end()
            return QIcon(pixmap)

else:

    class MiniHud:  # type: ignore[no-redef]
        def __init__(self, bridge: Any, parent: Any = None) -> None:
            raise RuntimeError("PySide6 is required for MiniHud")


    class TrayManager:  # type: ignore[no-redef]
        def __init__(self, main_window: Any, bridge: Any, parent: Any = None) -> None:
            raise RuntimeError("PySide6 is required for TrayManager")

        @staticmethod
        def is_available() -> bool:
            return False


__all__ = ["PYSIDE6_AVAILABLE", "MiniHud", "TrayManager"]
