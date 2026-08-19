from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QVBoxLayout,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QFrame = object  # type: ignore[misc,assignment]


class FansVoltagesCard(QFrame):
    """Card widget displaying active Fan speeds (RPM) and System Voltage rails."""

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setProperty("class", "card")

        self._fans: dict[str, tuple[QLabel, QProgressBar]] = {}
        self._voltages: dict[str, QLabel] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Title
        title = QLabel("COOLING FANS & VOLTAGE RAILS")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #90A4AE;")
        layout.addWidget(title)

        # --- Section A: Fans ---
        lbl_fans_hdr = QLabel("Cooling Fans")
        lbl_fans_hdr.setStyleSheet("font-weight: 700; color: #F0F6FC; font-size: 12px;")
        layout.addWidget(lbl_fans_hdr)

        self.fans_container = QVBoxLayout()
        self.fans_container.setSpacing(6)
        self.lbl_no_fans = QLabel("Passive Cooling / No active fans detected")
        self.lbl_no_fans.setStyleSheet(
            "color: #607D8B; font-size: 11px; font-style: italic;"
        )
        self.fans_container.addWidget(self.lbl_no_fans)
        layout.addLayout(self.fans_container)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #202A3C; max-height: 1px;")
        layout.addWidget(divider)

        # --- Section B: Voltages ---
        lbl_volts_hdr = QLabel("Power Rails")
        lbl_volts_hdr.setStyleSheet(
            "font-weight: 700; color: #F0F6FC; font-size: 12px;"
        )
        layout.addWidget(lbl_volts_hdr)

        self.volts_grid = QGridLayout()
        self.volts_grid.setSpacing(8)
        self.lbl_no_volts = QLabel("Voltage rails monitored via LHM on Windows")
        self.lbl_no_volts.setStyleSheet(
            "color: #607D8B; font-size: 11px; font-style: italic;"
        )
        self.volts_grid.addWidget(self.lbl_no_volts, 0, 0, 1, 2)
        layout.addLayout(self.volts_grid)

    def update_snapshot(self, snapshot: Any) -> None:
        """Parse fan speed (RPM) and voltage readings from snapshot."""
        if (
            not PYSIDE6_AVAILABLE
            or snapshot is None
            or not hasattr(snapshot, "readings")
        ):
            return

        fan_readings = []
        voltage_readings = []

        for r in snapshot.readings:
            is_fan = (
                r.metric.startswith("fan.speed")
                or "fan" in r.metric
                or (hasattr(r, "unit") and getattr(r.unit, "name", "") == "RPM")
            )
            if is_fan:
                fan_readings.append(r)
            elif r.metric.startswith("voltage."):
                voltage_readings.append(r)

        # Update Fans
        if fan_readings:
            self.lbl_no_fans.setVisible(False)
            for r in fan_readings:
                if r.tags:
                    fan_name = r.tags.get("fan") or r.tags.get("sensor") or r.metric
                else:
                    fan_name = r.metric.replace("system.fan.speed", "Fan").replace(
                        "fan.speed.", "Fan "
                    )
                key = f"{r.metric}:{fan_name}"
                rpm = float(r.value)

                if key not in self._fans:
                    row_layout = QHBoxLayout()
                    lbl_name = QLabel(fan_name)
                    lbl_name.setStyleSheet(
                        "font-size: 11px; font-weight: 600; "
                        "color: #F0F6FC; min-width: 80px;"
                    )
                    lbl_val = QLabel(f"{rpm:.0f} RPM")
                    lbl_val.setStyleSheet(
                        "font-size: 11px; font-weight: 700; "
                        "color: #00E5FF; min-width: 70px;"
                    )

                    bar = QProgressBar()
                    bar.setRange(0, 6000)  # Standard max RPM
                    bar.setValue(int(rpm))
                    bar.setTextVisible(False)
                    bar.setMaximumHeight(6)
                    bar.setStyleSheet(
                        "QProgressBar::chunk { background-color: #00E5FF; "
                        "border-radius: 2px; }"
                    )

                    row_layout.addWidget(lbl_name)
                    row_layout.addWidget(bar, stretch=1)
                    row_layout.addWidget(lbl_val, alignment=Qt.AlignmentFlag.AlignRight)
                    self.fans_container.addLayout(row_layout)
                    self._fans[key] = (lbl_val, bar)
                    self._fans[r.metric] = (lbl_val, bar)
                else:
                    lbl_val, bar = self._fans[key]
                    lbl_val.setText(f"{rpm:.0f} RPM")
                    bar.setValue(int(rpm))

        # Update Voltages
        if voltage_readings:
            self.lbl_no_volts.setVisible(False)
            for _i, r in enumerate(voltage_readings):
                key = r.metric
                volts = float(r.value)
                rail_name = key.replace("voltage.", "").replace("_", ".").upper()

                if key not in self._voltages:
                    lbl_name = QLabel(rail_name)
                    lbl_name.setStyleSheet(
                        "font-size: 11px; font-weight: 600; color: #90A4AE;"
                    )
                    lbl_val = QLabel(f"{volts:.2f} V")
                    lbl_val.setStyleSheet(
                        "font-size: 11px; font-weight: 700; color: #FFD600;"
                    )

                    row = len(self._voltages) // 2
                    col = (len(self._voltages) % 2) * 2
                    self.volts_grid.addWidget(lbl_name, row, col)
                    self.volts_grid.addWidget(lbl_val, row, col + 1)
                    self._voltages[key] = lbl_val
                else:
                    self._voltages[key].setText(f"{volts:.2f} V")
