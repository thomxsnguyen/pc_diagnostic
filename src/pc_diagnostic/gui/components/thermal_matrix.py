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

        title = QLabel("HARDWARE THERMAL MATRIX")
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
        sensor_tag = tags.get("sensor") or tags.get("name")
        if sensor_tag:
            name = sensor_tag
        else:
            name = (
                metric.replace("system.temperature.", "")
                .replace("thermal.", "")
                .replace("_", " ")
                .title()
            )

        metric_lower = metric.lower()
        name_lower = name.lower()

        if "gpu" in metric_lower or "gpu" in name_lower or "tdev" in name_lower:
            group = "GPU"
        elif (
            "cpu" in metric_lower
            or "core" in name_lower
            or "pmu" in name_lower
            or "tdie" in name_lower
            or "tcal" in name_lower
            or "soc" in name_lower
        ):
            group = "CPU"
        elif (
            "disk" in metric_lower
            or "ssd" in name_lower
            or "drive" in name_lower
            or "nand" in name_lower
            or "storage" in metric_lower
        ):
            group = "Storage"
        elif "battery" in name_lower or "battery" in metric_lower:
            group = "Battery"
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
            is_thermal = (
                r.metric.startswith("thermal.")
                or r.metric.startswith("system.temperature.")
                or (hasattr(r, "unit") and getattr(r.unit, "name", "") == "CELSIUS")
            )
            if not is_thermal:
                continue

            sensor_id = r.tags.get("sensor") if r.tags else None
            metric_key = f"{r.metric}:{sensor_id}" if sensor_id else r.metric
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
