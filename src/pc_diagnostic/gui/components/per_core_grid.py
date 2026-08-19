from __future__ import annotations

from typing import Any

try:
    from PySide6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QFrame = object  # type: ignore[misc,assignment]


class CoreCell(QWidget):
    """Mini widget displaying single CPU core utilization and label."""

    def __init__(self, core_idx: int, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)

        self.core_idx = core_idx
        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        self.lbl_name = QLabel(f"Core {self.core_idx:02d}")
        self.lbl_name.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #90A4AE;"
        )
        self.lbl_val = QLabel("0.0%")
        self.lbl_val.setStyleSheet("font-size: 11px; font-weight: 700; color: #F0F6FC;")

        header_row.addWidget(self.lbl_name)
        header_row.addStretch()
        header_row.addWidget(self.lbl_val)
        layout.addLayout(header_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setMaximumHeight(6)
        layout.addWidget(self.bar)

    def set_value(self, val: float) -> None:
        """Update core percentage value and dynamic color."""
        if not PYSIDE6_AVAILABLE:
            return

        clamped = max(0.0, min(100.0, val))
        self.lbl_val.setText(f"{clamped:.1f}%")
        self.bar.setValue(int(clamped))

        if clamped >= 80.0:
            chunk_color = "#FF1744"
        elif clamped >= 50.0:
            chunk_color = "#FFD600"
        else:
            chunk_color = "#00E5FF"

        style = (
            "QProgressBar { border: none; background-color: #151C29; "
            "border-radius: 2px; } "
            f"QProgressBar::chunk {{ background-color: {chunk_color}; "
            "border-radius: 2px; }}"
        )
        self.bar.setStyleSheet(style)


class PerCoreGridWidget(QFrame):
    """Card widget rendering a dynamic grid of all logical CPU cores."""

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setProperty("class", "card")

        self._cores: dict[int, CoreCell] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Header Row
        header_layout = QHBoxLayout()
        title = QLabel("PER-CORE CPU UTILIZATION")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #90A4AE;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.lbl_core_count = QLabel("0 Cores")
        self.lbl_core_count.setStyleSheet(
            "background-color: #1C2536; color: #00E5FF; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        header_layout.addWidget(self.lbl_core_count)
        layout.addLayout(header_layout)

        # Core Grid Container
        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        layout.addLayout(self.grid)

    def update_snapshot(self, snapshot: Any) -> None:
        """Parse per-core utilization metrics from snapshot and update grid cells."""
        if (
            not PYSIDE6_AVAILABLE
            or snapshot is None
            or not hasattr(snapshot, "readings")
        ):
            return

        core_readings: list[tuple[int, float]] = []

        for r in snapshot.readings:
            if r.metric.startswith("cpu.utilization.core."):
                try:
                    core_idx = int(r.metric.split(".")[-1])
                    core_readings.append((core_idx, r.value))
                except (ValueError, IndexError):
                    continue
            elif (
                r.metric in ["cpu.utilization.per_core", "cpu.utilization.core"]
                and r.tags
                and "core" in r.tags
            ):
                try:
                    core_idx = int(r.tags["core"])
                    core_readings.append((core_idx, r.value))
                except (ValueError, TypeError):
                    continue

        if not core_readings:
            return

        core_readings.sort(key=lambda x: x[0])
        total_cores = len(core_readings)
        self.lbl_core_count.setText(f"{total_cores} Cores")

        cols = 4 if total_cores >= 8 else 2

        for core_idx, val in core_readings:
            if core_idx not in self._cores:
                cell = CoreCell(core_idx, self)
                row = core_idx // cols
                col = core_idx % cols
                self.grid.addWidget(cell, row, col)
                self._cores[core_idx] = cell

            self._cores[core_idx].set_value(val)
