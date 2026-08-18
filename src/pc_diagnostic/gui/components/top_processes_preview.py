from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QFrame,
        QHeaderView,
        QLabel,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QFrame = object  # type: ignore[misc,assignment]


class TopProcessesPreview(QFrame):
    """Compact live preview table for Top CPU and Memory consuming processes."""

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setProperty("class", "card")

        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header Title
        title = QLabel("⚡ TOP ACTIVE PROCESSES")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #90A4AE;")
        layout.addWidget(title)

        # Table Widget
        self.table = QTableWidget(5, 4)
        self.table.setHorizontalHeaderLabels(["PID", "Process Name", "CPU %", "RAM"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "background-color: transparent; border: none; font-size: 11px;"
        )

        # Populate empty placeholder rows
        for row in range(5):
            for col in range(4):
                item = QTableWidgetItem("—")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter
                    | (
                        Qt.AlignmentFlag.AlignLeft
                        if col == 1
                        else Qt.AlignmentFlag.AlignCenter
                    )
                )
                self.table.setItem(row, col, item)

        layout.addWidget(self.table)

    def update_snapshot(self, snapshot: Any) -> None:
        """Parse top process readings from snapshot and populate table."""
        if (
            not PYSIDE6_AVAILABLE
            or snapshot is None
            or not hasattr(snapshot, "readings")
        ):
            return

        cpu_procs = []
        for r in snapshot.readings:
            if r.tags and r.tags.get("type") == "cpu_top":
                pid = r.tags.get("pid", "0")
                name = r.tags.get("name", "Unknown")
                mem_str = r.tags.get("mem_str", "—")
                cpu_val = f"{r.value:.1f}%"
                cpu_procs.append((pid, name, cpu_val, mem_str))

        # Update table rows
        for row in range(5):
            if row < len(cpu_procs):
                pid, name, cpu_val, mem_str = cpu_procs[row]
                self._set_item(row, 0, pid)
                self._set_item(row, 1, name)
                self._set_item(row, 2, cpu_val, color="#00E5FF")
                self._set_item(row, 3, mem_str, color="#7C4DFF")
            else:
                for col in range(4):
                    self._set_item(row, col, "—")

    def _set_item(
        self, row: int, col: int, text: str, color: str | None = None
    ) -> None:
        item = self.table.item(row, col)
        if item is not None:
            item.setText(text)
            if color:
                item.setForeground(Qt.GlobalColor.white)
