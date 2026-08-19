from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pc_diagnostic.alerts.models import Incident
    from pc_diagnostic.gui.bridge import TelemetryBridge

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QPushButton,
        QScrollArea,
        QSlider,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class AlertsView(QWidget):
    """Active Alerting & Incident Management View featuring real-time incident logs

    and interactive threshold / hysteresis rule configuration sliders.
    """

    def __init__(self, bridge: TelemetryBridge, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
        self.bridge = bridge
        self._incidents_history: list[dict[str, Any]] = []

        # Current rule threshold states
        self.cpu_threshold = 90.0
        self.mem_threshold = 90.0
        self.debounce_s = 5.0
        self.hysteresis = 10.0

        self._init_ui()

        # Connect to TelemetryBridge alert signal
        self.bridge.alert_triggered.connect(self._on_alert_triggered)

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 16, 20, 20)
        main_layout.setSpacing(16)

        # 1. Active Incidents Log Card
        incidents_card = self._build_incidents_card()
        main_layout.addWidget(incidents_card)

        # 2. Alert Threshold Sliders Card
        config_card = self._build_config_card()
        main_layout.addWidget(config_card)

        scroll.setWidget(container)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

    def _build_incidents_card(self) -> QFrame:
        """Create the incident table card."""
        card = QFrame(self)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel("ACTIVE & RECENT INCIDENTS")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #A6ABB3;")
        header_row.addWidget(title)

        header_row.addStretch()

        self.btn_clear_log = QPushButton("Clear Incident History")
        self.btn_clear_log.setStyleSheet(
            "QPushButton { background-color: #1C1F24; color: #A6ABB3; "
            "border: 1px solid #30343B; border-radius: 4px; padding: 4px 10px; "
            "font-size: 11px; } "
            "QPushButton:hover { background-color: #24272D; color: #ECEEF1; }"
        )
        self.btn_clear_log.clicked.connect(self._clear_incidents)
        header_row.addWidget(self.btn_clear_log)
        layout.addLayout(header_row)

        # Incidents Table
        self.incidents_table = QTableWidget(0, 5)
        self.incidents_table.setHorizontalHeaderLabels(
            ["Timestamp", "Rule ID", "State", "Trigger Value", "Threshold"]
        )
        self.incidents_table.verticalHeader().setVisible(False)
        self.incidents_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.incidents_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.incidents_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.incidents_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.incidents_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.incidents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.incidents_table.setShowGrid(False)
        self.incidents_table.setMinimumHeight(180)
        self.incidents_table.setStyleSheet(
            "background-color: transparent; border: none; font-size: 11px;"
        )

        layout.addWidget(self.incidents_table)
        return card

    def _build_config_card(self) -> QFrame:
        """Create the interactive threshold configuration sliders card."""
        card = QFrame(self)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        title = QLabel("THRESHOLD & DEBOUNCE CONFIGURATION")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #A6ABB3;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(12)

        # Slider 1: CPU Threshold
        lbl_cpu = QLabel("High CPU Threshold")
        lbl_cpu.setStyleSheet("color: #ECEEF1; font-weight: 600; font-size: 12px;")
        self.lbl_cpu_val = QLabel(f"{int(self.cpu_threshold)}%")
        self.lbl_cpu_val.setStyleSheet(
            "color: #93C5FD; font-weight: 700; font-size: 12px;"
        )
        self.slider_cpu = QSlider(Qt.Orientation.Horizontal)
        self.slider_cpu.setRange(50, 99)
        self.slider_cpu.setValue(int(self.cpu_threshold))
        self.slider_cpu.valueChanged.connect(self._on_cpu_slider_changed)

        grid.addWidget(lbl_cpu, 0, 0)
        grid.addWidget(self.lbl_cpu_val, 0, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.slider_cpu, 1, 0, 1, 2)

        # Slider 2: Memory Threshold
        lbl_mem = QLabel("High Memory Threshold")
        lbl_mem.setStyleSheet("color: #ECEEF1; font-weight: 600; font-size: 12px;")
        self.lbl_mem_val = QLabel(f"{int(self.mem_threshold)}%")
        self.lbl_mem_val.setStyleSheet(
            "color: #A6ABB3; font-weight: 700; font-size: 12px;"
        )
        self.slider_mem = QSlider(Qt.Orientation.Horizontal)
        self.slider_mem.setRange(50, 99)
        self.slider_mem.setValue(int(self.mem_threshold))
        self.slider_mem.valueChanged.connect(self._on_mem_slider_changed)

        grid.addWidget(lbl_mem, 2, 0)
        grid.addWidget(self.lbl_mem_val, 2, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.slider_mem, 3, 0, 1, 2)

        # Slider 3: Debounce Duration
        lbl_debounce = QLabel("Debounce Duration (Hold Time)")
        lbl_debounce.setStyleSheet("color: #ECEEF1; font-weight: 600; font-size: 12px;")
        self.lbl_debounce_val = QLabel(f"{int(self.debounce_s)}s")
        self.lbl_debounce_val.setStyleSheet(
            "color: #FFD600; font-weight: 700; font-size: 12px;"
        )
        self.slider_debounce = QSlider(Qt.Orientation.Horizontal)
        self.slider_debounce.setRange(1, 30)
        self.slider_debounce.setValue(int(self.debounce_s))
        self.slider_debounce.valueChanged.connect(self._on_debounce_slider_changed)

        grid.addWidget(lbl_debounce, 4, 0)
        grid.addWidget(self.lbl_debounce_val, 4, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.slider_debounce, 5, 0, 1, 2)

        # Slider 4: Hysteresis Margin
        lbl_hysteresis = QLabel("Clear Hysteresis Margin")
        lbl_hysteresis.setStyleSheet(
            "color: #ECEEF1; font-weight: 600; font-size: 12px;"
        )
        self.lbl_hysteresis_val = QLabel(f"{int(self.hysteresis)}%")
        self.lbl_hysteresis_val.setStyleSheet(
            "color: #00E676; font-weight: 700; font-size: 12px;"
        )
        self.slider_hysteresis = QSlider(Qt.Orientation.Horizontal)
        self.slider_hysteresis.setRange(1, 15)
        self.slider_hysteresis.setValue(int(self.hysteresis))
        self.slider_hysteresis.valueChanged.connect(self._on_hysteresis_slider_changed)

        grid.addWidget(lbl_hysteresis, 6, 0)
        grid.addWidget(self.lbl_hysteresis_val, 6, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.slider_hysteresis, 7, 0, 1, 2)

        layout.addLayout(grid)
        return card

    def _on_cpu_slider_changed(self, val: int) -> None:
        self.cpu_threshold = float(val)
        self.lbl_cpu_val.setText(f"{val}%")
        self.bridge.update_rule_threshold(
            "high_cpu",
            threshold=self.cpu_threshold,
            duration_s=self.debounce_s,
            hysteresis_offset=self.hysteresis,
        )

    def _on_mem_slider_changed(self, val: int) -> None:
        self.mem_threshold = float(val)
        self.lbl_mem_val.setText(f"{val}%")
        self.bridge.update_rule_threshold(
            "high_memory",
            threshold=self.mem_threshold,
            duration_s=self.debounce_s,
            hysteresis_offset=self.hysteresis,
        )

    def _on_debounce_slider_changed(self, val: int) -> None:
        self.debounce_s = float(val)
        self.lbl_debounce_val.setText(f"{val}s")
        self.bridge.update_rule_threshold(
            "high_cpu",
            threshold=self.cpu_threshold,
            duration_s=self.debounce_s,
            hysteresis_offset=self.hysteresis,
        )
        self.bridge.update_rule_threshold(
            "high_memory",
            threshold=self.mem_threshold,
            duration_s=self.debounce_s,
            hysteresis_offset=self.hysteresis,
        )

    def _on_hysteresis_slider_changed(self, val: int) -> None:
        self.hysteresis = float(val)
        self.lbl_hysteresis_val.setText(f"{val}%")
        self.bridge.update_rule_threshold(
            "high_cpu",
            threshold=self.cpu_threshold,
            duration_s=self.debounce_s,
            hysteresis_offset=self.hysteresis,
        )
        self.bridge.update_rule_threshold(
            "high_memory",
            threshold=self.mem_threshold,
            duration_s=self.debounce_s,
            hysteresis_offset=self.hysteresis,
        )

    def _clear_incidents(self) -> None:
        """Clear historical entries in the incident table."""
        self._incidents_history.clear()
        if PYSIDE6_AVAILABLE:
            self.incidents_table.setRowCount(0)

    def _on_alert_triggered(self, incident: Incident) -> None:
        """Handle incoming alert signal and append entry to incident log."""
        if not PYSIDE6_AVAILABLE or incident is None:
            return

        ts_str = time.strftime(
            "%H:%M:%S", time.localtime(incident.last_fired_at or time.time())
        )
        state_str = (
            incident.state.name
            if hasattr(incident.state, "name")
            else str(incident.state)
        )
        rule_id = incident.rule.id if hasattr(incident.rule, "id") else "alert"
        threshold_str = (
            f"{incident.rule.threshold:.1f}"
            if hasattr(incident.rule, "threshold")
            else "—"
        )
        val_str = f"{incident.value:.1f}"

        # Insert at row 0 (most recent on top)
        row_idx = 0
        self.incidents_table.insertRow(row_idx)

        t_item = QTableWidgetItem(ts_str)
        t_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.incidents_table.setItem(row_idx, 0, t_item)

        r_item = QTableWidgetItem(rule_id)
        r_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.incidents_table.setItem(row_idx, 1, r_item)

        s_item = QTableWidgetItem(state_str)
        s_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        if state_str == "FIRING":
            s_item.setForeground(Qt.GlobalColor.red)
        else:
            s_item.setForeground(Qt.GlobalColor.green)
        self.incidents_table.setItem(row_idx, 2, s_item)

        v_item = QTableWidgetItem(val_str)
        v_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self.incidents_table.setItem(row_idx, 3, v_item)

        th_item = QTableWidgetItem(threshold_str)
        th_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self.incidents_table.setItem(row_idx, 4, th_item)
