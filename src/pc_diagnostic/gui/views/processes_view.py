from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

try:
    import psutil  # type: ignore[import-untyped]
except ImportError:
    psutil = None

from pc_diagnostic.gui.components import ProcessTableWidget

if TYPE_CHECKING:
    from pc_diagnostic.gui.bridge import TelemetryBridge
    from pc_diagnostic.models import Snapshot

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


class ProcessesView(QWidget):
    """Process Inspector View offering real-time process monitoring,

    sorting, searching, and right-click process termination.
    """

    def __init__(self, bridge: TelemetryBridge, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
        self.bridge = bridge
        self._is_paused = False
        self._init_ui()

        # Connect to TelemetryBridge signals
        self.bridge.snapshot_updated.connect(self._on_snapshot)

        # Polling timer for updating full process list every 2 seconds
        if PYSIDE6_AVAILABLE:
            self._proc_timer = QTimer(self)
            self._proc_timer.timeout.connect(self._refresh_process_list)
            self._proc_timer.start(2000)

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        # 1. Top Summary Banner Card
        banner_card = QFrame(self)
        banner_card.setProperty("class", "card")
        banner_layout = QHBoxLayout(banner_card)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(20)

        # Left Info
        vbox_left = QVBoxLayout()
        title = QLabel("PROCESS INSPECTOR")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #ECEEF1;")
        self.lbl_summary = QLabel("Monitoring active threads & task resources")
        self.lbl_summary.setStyleSheet("color: #A6ABB3; font-size: 11px;")
        vbox_left.addWidget(title)
        vbox_left.addWidget(self.lbl_summary)
        banner_layout.addLayout(vbox_left, stretch=2)

        # Middle Highlights
        vbox_mid = QVBoxLayout()
        self.lbl_top_cpu = QLabel("Top CPU: —")
        self.lbl_top_cpu.setStyleSheet(
            "color: #93C5FD; font-size: 12px; font-weight: 600;"
        )
        self.lbl_top_mem = QLabel("Top RAM: —")
        self.lbl_top_mem.setStyleSheet(
            "color: #A6ABB3; font-size: 12px; font-weight: 600;"
        )
        vbox_mid.addWidget(self.lbl_top_cpu)
        vbox_mid.addWidget(self.lbl_top_mem)
        banner_layout.addLayout(vbox_mid, stretch=2)

        # Right Action Buttons
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setStyleSheet(
            "QPushButton { background-color: #1C1F24; color: #ECEEF1; "
            "border: 1px solid #30343B; border-radius: 4px; padding: 6px 14px; "
            "font-weight: 600; } "
            "QPushButton:hover { background-color: #24272D; }"
        )
        self.btn_pause.clicked.connect(self._toggle_pause)
        banner_layout.addWidget(self.btn_pause, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(banner_card)

        # 2. Main Process Table Widget
        self.process_table = ProcessTableWidget(self)
        layout.addWidget(self.process_table, stretch=1)

    def _toggle_pause(self) -> None:
        """Toggle live process table updating."""
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.btn_pause.setText("Resume")
            self.btn_pause.setStyleSheet(
                "QPushButton { background-color: #FFD600; color: #0B0E14; "
                "border-radius: 4px; padding: 6px 14px; font-weight: 700; }"
            )
        else:
            self.btn_pause.setText("Pause")
            self.btn_pause.setStyleSheet(
                "QPushButton { background-color: #1C1F24; color: #ECEEF1; "
                "border: 1px solid #30343B; border-radius: 4px; padding: 6px 14px; "
                "font-weight: 600; }"
            )

    def _on_snapshot(self, snapshot: Snapshot) -> None:
        """Extract top CPU and RAM processes from latest snapshot."""
        if not PYSIDE6_AVAILABLE or snapshot is None:
            return

        top_cpu_name = ""
        top_cpu_val = 0.0
        top_mem_name = ""
        top_mem_str = ""

        for r in snapshot.readings:
            if r.tags and r.tags.get("type") == "cpu_top":
                if r.metric == "process.cpu_percent" and r.value > top_cpu_val:
                    top_cpu_val = r.value
                    top_cpu_name = r.tags.get("name", "unknown")
            elif r.tags and r.tags.get("type") == "mem_top":
                if r.metric == "process.memory.used":
                    top_mem_name = r.tags.get("name", "unknown")
                    top_mem_str = r.tags.get(
                        "mem_str", f"{r.value / (1024 * 1024):.0f} MB"
                    )

        if top_cpu_name:
            self.lbl_top_cpu.setText(f"Top CPU: {top_cpu_name} ({top_cpu_val:.1f}%)")
        if top_mem_name:
            self.lbl_top_mem.setText(f"Top RAM: {top_mem_name} ({top_mem_str})")

    def _refresh_process_list(self) -> None:
        """Scan running system processes using psutil and feed to ProcessTableWidget."""
        if not PYSIDE6_AVAILABLE or self._is_paused or psutil is None:
            return

        try:
            procs = []
            for p in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_info", "status"]
            ):
                try:
                    info = p.info
                    pid = info["pid"]
                    name = info["name"] or "unknown"
                    cpu = float(info["cpu_percent"] or 0.0)
                    mem_bytes = info["memory_info"].rss if info["memory_info"] else 0
                    mem_mb = mem_bytes / (1024.0 * 1024.0)
                    status = str(info["status"] or "running")
                    procs.append((pid, name, cpu, mem_mb, status))
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue

            # Sort primarily by CPU descending
            procs.sort(key=lambda x: x[2], reverse=True)
            self.process_table.update_processes(procs)
        except Exception as e:
            logger.warning(f"Error gathering process list in ProcessesView: {e}")
