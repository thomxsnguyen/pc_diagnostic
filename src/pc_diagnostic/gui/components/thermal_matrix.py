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


class ThermalMatrixWidget(QFrame):
    """Structured table widget displaying hardware thermal sensors with session

    Min/Max tracking.
    """

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setProperty("class", "card")

        # metric_key -> {"name": str, "group": str, "min": float,
        #                "max": float, "current": float, "row": int}
        self._sensors: dict[str, dict[str, Any]] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("🌡️ HARDWARE THERMAL MATRIX")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #90A4AE;")
        layout.addWidget(title)

        subtitle = QLabel("Monitored via macOS SMC/HID or Windows LibreHardwareMonitor")
        subtitle.setStyleSheet("color: #607D8B; font-size: 11px;")
        layout.addWidget(subtitle)

        # Table Widget
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Group", "Sensor Name", "Current", "Min", "Max", "Status"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "background-color: transparent; border: none; font-size: 11px;"
        )

        layout.addWidget(self.table)

    def _determine_group_and_name(
        self, metric: str, tags: dict[str, str]
    ) -> tuple[str, str]:
        """Categorize sensor into Group (CPU, GPU, Storage, System) and name."""
        name = (
            tags.get("name")
            or tags.get("sensor")
            or metric.replace("thermal.", "").replace("_", " ").title()
        )

        if "gpu" in metric.lower() or "gpu" in name.lower():
            group = "GPU"
        elif "cpu" in metric.lower() or "core" in name.lower() or "pmu" in name.lower():
            group = "CPU"
        elif (
            "disk" in metric.lower() or "ssd" in name.lower() or "drive" in name.lower()
        ):
            group = "Storage"
        else:
            group = "System"

        return group, name

    def update_snapshot(self, snapshot: Any) -> None:
        """Parse temperature readings from snapshot and update min/max table."""
        if (
            not PYSIDE6_AVAILABLE
            or snapshot is None
            or not hasattr(snapshot, "readings")
        ):
            return

        for r in snapshot.readings:
            if not r.metric.startswith("thermal."):
                continue

            metric_key = r.metric
            val = float(r.value)
            tags = r.tags if r.tags else {}

            if metric_key not in self._sensors:
                group, friendly_name = self._determine_group_and_name(metric_key, tags)
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)

                # Initialize table row items
                for col in range(6):
                    item = QTableWidgetItem()
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter
                        | (
                            Qt.AlignmentFlag.AlignLeft
                            if col in [0, 1]
                            else Qt.AlignmentFlag.AlignCenter
                        )
                    )
                    self.table.setItem(row_idx, col, item)

                self._sensors[metric_key] = {
                    "name": friendly_name,
                    "group": group,
                    "min": val,
                    "max": val,
                    "current": val,
                    "row": row_idx,
                }
            else:
                s = self._sensors[metric_key]
                s["current"] = val
                s["min"] = min(s["min"], val)
                s["max"] = max(s["max"], val)

            # Update row in UI
            s = self._sensors[metric_key]
            row = s["row"]

            self.table.item(row, 0).setText(s["group"])
            self.table.item(row, 1).setText(s["name"])
            self.table.item(row, 2).setText(f"{s['current']:.1f} °C")
            self.table.item(row, 3).setText(f"{s['min']:.1f} °C")
            self.table.item(row, 4).setText(f"{s['max']:.1f} °C")

            # Determine status badge
            if s["current"] >= 85.0:
                status_text = "HOT"
            elif s["current"] >= 65.0:
                status_text = "WARM"
            else:
                status_text = "NORMAL"

            self.table.item(row, 5).setText(status_text)
