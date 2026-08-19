from __future__ import annotations

import logging
import os
import signal
from typing import Any

try:
    import psutil  # type: ignore[import-untyped]
except ImportError:
    psutil = None

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


class NumericTableWidgetItem(QTableWidgetItem if PYSIDE6_AVAILABLE else object):  # type: ignore[misc]
    """QTableWidgetItem that sorts numerically instead of alphabetically."""

    def __init__(self, value: float | int, display_text: str) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(display_text)
            self._num_value = float(value)
            self.setData(Qt.ItemDataRole.UserRole, self._num_value)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, NumericTableWidgetItem):
            return self._num_value < other._num_value
        return super().__lt__(other)


class ProcessTableWidget(QWidget):
    """High-performance sortable & searchable process inspection table."""

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)

        self._filter_query = ""
        self._is_updating = False
        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Toolbar: Search Bar + Process Counter
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search processes by name or PID...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input, stretch=2)

        self.lbl_process_count = QLabel("0 Running")
        self.lbl_process_count.setStyleSheet(
            "background-color: #1C1F24; color: #93C5FD; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: 600;"
        )
        toolbar.addWidget(self.lbl_process_count)
        layout.addLayout(toolbar)

        # Table Widget
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["PID", "Process Name", "CPU %", "Memory (MB)", "Status"]
        )
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in ((0, 80), (2, 85), (3, 110), (4, 90)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setWordWrap(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def _on_search_changed(self, text: str) -> None:
        """Filter table rows based on PID or process name."""
        self._filter_query = text.strip().lower()
        self._apply_filter()

    def _apply_filter(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        visible_count = 0
        for row in range(self.table.rowCount()):
            pid_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)

            if not pid_item or not name_item:
                continue

            pid_str = pid_item.text().lower()
            name_str = name_item.text().lower()

            if (
                not self._filter_query
                or self._filter_query in pid_str
                or self._filter_query in name_str
            ):
                self.table.setRowHidden(row, False)
                visible_count += 1
            else:
                self.table.setRowHidden(row, True)

        self.lbl_process_count.setText(f"{visible_count} Processes")

    def update_processes(
        self,
        procs: list[tuple[int, str, float, float, str]],
    ) -> None:
        """Update table with latest process records."""
        if not PYSIDE6_AVAILABLE or self._is_updating:
            return

        self._is_updating = True
        updates_enabled = self.table.updatesEnabled()
        signals_blocked = self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        try:
            current_row_count = self.table.rowCount()
            target_row_count = len(procs)

            if current_row_count != target_row_count:
                self.table.setRowCount(target_row_count)

            for row, (pid, name, cpu_pct, mem_mb, status) in enumerate(procs):
                # PID
                pid_item = NumericTableWidgetItem(pid, str(pid))
                pid_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                self.table.setItem(row, 0, pid_item)

                # Name
                name_item = QTableWidgetItem(name)
                name_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                self.table.setItem(row, 1, name_item)

                # CPU %
                cpu_item = NumericTableWidgetItem(cpu_pct, f"{cpu_pct:.1f}%")
                cpu_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                )
                self.table.setItem(row, 2, cpu_item)

                # Memory (MB)
                mem_item = NumericTableWidgetItem(mem_mb, f"{mem_mb:.1f} MB")
                mem_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                )
                self.table.setItem(row, 3, mem_item)

                # Status
                status_item = QTableWidgetItem(status.capitalize())
                status_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
                )
                self.table.setItem(row, 4, status_item)

            self._apply_filter()
        finally:
            self.table.setSortingEnabled(True)
            self.table.blockSignals(signals_blocked)
            self.table.setUpdatesEnabled(updates_enabled)
            self._is_updating = False

    def _show_context_menu(self, pos: Any) -> None:
        """Render right-click context menu for process management actions."""
        if not PYSIDE6_AVAILABLE:
            return

        item = self.table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        pid_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)

        if not pid_item or not name_item:
            return

        try:
            pid = int(pid_item.text())
        except ValueError:
            return

        proc_name = name_item.text()

        menu = QMenu(self)
        action_term = menu.addAction(f"Terminate '{proc_name}' (SIGTERM)")
        action_kill = menu.addAction(f"Force Kill '{proc_name}' (SIGKILL)")

        selected_action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if selected_action == action_term:
            self._terminate_pid(pid, proc_name, force=False)
        elif selected_action == action_kill:
            self._terminate_pid(pid, proc_name, force=True)

    def _terminate_pid(self, pid: int, name: str, force: bool = False) -> bool:
        """Send termination signal to process with error dialog fallback."""
        try:
            if psutil is not None:
                p = psutil.Process(pid)
                if force:
                    p.kill()
                else:
                    p.terminate()
            else:
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(pid, sig)
            action_name = "SIGKILL" if force else "SIGTERM"
            logger.info(f"Successfully sent {action_name} to PID {pid} ({name})")
            return True
        except (
            ProcessLookupError,
            getattr(psutil, "NoSuchProcess", ProcessLookupError),
        ):
            logger.warning(f"Process PID {pid} no longer exists.")
            return False
        except (
            PermissionError,
            getattr(psutil, "AccessDenied", PermissionError),
        ) as e:
            logger.warning(f"Permission denied killing PID {pid}: {e}")
            if PYSIDE6_AVAILABLE:
                QMessageBox.warning(
                    self,
                    "Permission Denied",
                    f"Insufficient permissions to terminate {name} (PID {pid}).\n"
                    "Run with elevated privileges.",
                )
            return False
        except Exception as e:
            logger.error(f"Error terminating PID {pid}: {e}")
            return False
