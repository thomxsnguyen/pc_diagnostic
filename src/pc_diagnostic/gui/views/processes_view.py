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
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # 1. Page status header
        banner_card = QFrame(self)
        banner_card.setProperty("class", "card")
        banner_layout = QHBoxLayout(banner_card)
        banner_layout.setContentsMargins(18, 14, 18, 14)
        banner_layout.setSpacing(18)

        vbox_left = QVBoxLayout()
        vbox_left.setSpacing(4)
        title = QLabel("Processes")
        title.setObjectName("process_page_title")
        self.lbl_summary = QLabel("Live process activity and resource usage")
        self.lbl_summary.setObjectName("process_page_subtitle")
        vbox_left.addWidget(title)
        vbox_left.addWidget(self.lbl_summary)
        banner_layout.addLayout(vbox_left, stretch=1)

        cpu_column = QVBoxLayout()
        cpu_column.setSpacing(3)
        cpu_caption = QLabel("TOP CPU")
        cpu_caption.setObjectName("process_stat_label")
        self.lbl_top_cpu = QLabel("—")
        self.lbl_top_cpu.setObjectName("process_stat_value")
        self.lbl_top_cpu.setMaximumWidth(210)
        cpu_column.addWidget(cpu_caption)
        cpu_column.addWidget(self.lbl_top_cpu)
        banner_layout.addLayout(cpu_column)

        memory_column = QVBoxLayout()
        memory_column.setSpacing(3)
        memory_caption = QLabel("TOP MEMORY")
        memory_caption.setObjectName("process_stat_label")
        self.lbl_top_mem = QLabel("—")
        self.lbl_top_mem.setObjectName("process_stat_value")
        self.lbl_top_mem.setMaximumWidth(210)
        memory_column.addWidget(memory_caption)
        memory_column.addWidget(self.lbl_top_mem)
        banner_layout.addLayout(memory_column)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setObjectName("process_pause")
        self.btn_pause.setProperty("class", "secondary_btn")
        self.btn_pause.setProperty("paused", False)
        self.btn_pause.setMinimumWidth(92)
        self.btn_pause.clicked.connect(self._toggle_pause)
        banner_layout.addWidget(self.btn_pause, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(banner_card)

        # 2. Process workspace
        table_card = QFrame(self)
        table_card.setProperty("class", "card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        table_title = QLabel("Running processes")
        table_title.setObjectName("process_section_title")
        table_subtitle = QLabel("Search, sort, or right-click a process for actions")
        table_subtitle.setObjectName("process_section_subtitle")
        table_layout.addWidget(table_title)
        table_layout.addWidget(table_subtitle)

        self.process_table = ProcessTableWidget(table_card)
        table_layout.addWidget(self.process_table, stretch=1)
        layout.addWidget(table_card, stretch=1)

    def _toggle_pause(self) -> None:
        """Toggle live process table updating."""
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.btn_pause.setText("Resume")
        else:
            self.btn_pause.setText("Pause")
        self.btn_pause.setProperty("paused", self._is_paused)
        self.btn_pause.style().unpolish(self.btn_pause)
        self.btn_pause.style().polish(self.btn_pause)

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
            self.lbl_top_cpu.setText(f"{top_cpu_name} · {top_cpu_val:.1f}%")
        if top_mem_name:
            self.lbl_top_mem.setText(f"{top_mem_name} · {top_mem_str}")

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
