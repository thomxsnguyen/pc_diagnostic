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
        scroll.setObjectName("alerts_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("alerts_root")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(16)

        # Active incidents
        incidents_card = self._build_incidents_card()
        main_layout.addWidget(incidents_card, stretch=1)

        # Alert thresholds
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
        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        title = QLabel("Incident history")
        title.setObjectName("alerts_section_title")
        subtitle = QLabel("Active and recently triggered alert rules")
        subtitle.setObjectName("alerts_section_subtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header_row.addLayout(title_column)

        header_row.addStretch()

        self.btn_clear_log = QPushButton("Clear history")
        self.btn_clear_log.setProperty("class", "secondary_btn")
        self.btn_clear_log.clicked.connect(self._clear_incidents)
        header_row.addWidget(self.btn_clear_log)
        layout.addLayout(header_row)

        # Incidents Table
        self.incidents_table = QTableWidget(0, 5)
        self.incidents_table.setObjectName("alerts_incidents_table")
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
        layout.addWidget(self.incidents_table)
        return card

    def _build_config_card(self) -> QFrame:
        """Create the interactive threshold configuration sliders card."""
        card = QFrame(self)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        title = QLabel("Threshold configuration")
        title.setObjectName("alerts_section_title")
        layout.addWidget(title)

        subtitle = QLabel("Tune when resource alerts activate and clear")
        subtitle.setObjectName("alerts_section_subtitle")
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(12)

        # Slider 1: CPU Threshold
        self.lbl_cpu_val = QLabel(f"{int(self.cpu_threshold)}%")
        self.slider_cpu = QSlider(Qt.Orientation.Horizontal)
        self.slider_cpu.setRange(50, 99)
        self.slider_cpu.setValue(int(self.cpu_threshold))
        self.slider_cpu.valueChanged.connect(self._on_cpu_slider_changed)
        grid.addWidget(
            self._build_slider_control(
                "High CPU threshold",
                "Alert when total CPU usage remains above this level",
                self.lbl_cpu_val,
                self.slider_cpu,
            ),
            0,
            0,
        )

        # Slider 2: Memory Threshold
        self.lbl_mem_val = QLabel(f"{int(self.mem_threshold)}%")
        self.slider_mem = QSlider(Qt.Orientation.Horizontal)
        self.slider_mem.setRange(50, 99)
        self.slider_mem.setValue(int(self.mem_threshold))
        self.slider_mem.valueChanged.connect(self._on_mem_slider_changed)
        grid.addWidget(
            self._build_slider_control(
                "High memory threshold",
                "Alert when memory usage remains above this level",
                self.lbl_mem_val,
                self.slider_mem,
            ),
            0,
            1,
        )

        # Slider 3: Debounce Duration
        self.lbl_debounce_val = QLabel(f"{int(self.debounce_s)}s")
        self.slider_debounce = QSlider(Qt.Orientation.Horizontal)
        self.slider_debounce.setRange(1, 30)
        self.slider_debounce.setValue(int(self.debounce_s))
        self.slider_debounce.valueChanged.connect(self._on_debounce_slider_changed)
        grid.addWidget(
            self._build_slider_control(
                "Debounce duration",
                "Required hold time before an alert activates",
                self.lbl_debounce_val,
                self.slider_debounce,
            ),
            1,
            0,
        )

        # Slider 4: Hysteresis Margin
        self.lbl_hysteresis_val = QLabel(f"{int(self.hysteresis)}%")
        self.slider_hysteresis = QSlider(Qt.Orientation.Horizontal)
        self.slider_hysteresis.setRange(1, 15)
        self.slider_hysteresis.setValue(int(self.hysteresis))
        self.slider_hysteresis.valueChanged.connect(self._on_hysteresis_slider_changed)
        grid.addWidget(
            self._build_slider_control(
                "Clear hysteresis margin",
                "Required recovery margin before an alert clears",
                self.lbl_hysteresis_val,
                self.slider_hysteresis,
            ),
            1,
            1,
        )

        layout.addLayout(grid)
        return card

    def _build_slider_control(
        self,
        title_text: str,
        description: str,
        value_label: QLabel,
        slider: QSlider,
    ) -> QFrame:
        """Build one compact threshold control without changing rule behavior."""
        panel = QFrame(self)
        panel.setObjectName("alert_control_panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(5)

        title_row = QHBoxLayout()
        title = QLabel(title_text)
        title.setObjectName("alert_control_title")
        value_label.setObjectName("alert_control_value")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(value_label)
        panel_layout.addLayout(title_row)

        helper = QLabel(description)
        helper.setObjectName("alert_control_description")
        panel_layout.addWidget(helper)

        slider.setObjectName("alert_slider")
        slider.setMinimumHeight(28)
        panel_layout.addWidget(slider)
        return panel

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
