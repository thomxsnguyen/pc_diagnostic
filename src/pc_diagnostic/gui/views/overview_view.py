from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pc_diagnostic.gui.components import (
    RadialGaugeWidget,
    StorageNetworkCard,
    TimeSeriesChart,
    TopProcessesPreview,
)

if TYPE_CHECKING:
    from pc_diagnostic.gui.bridge import TelemetryBridge
    from pc_diagnostic.models import Snapshot

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class OverviewView(QWidget):
    """System Overview Dashboard View featuring radial gauges, real-time vector

    history charts, storage/network I/O counters, and live top processes.
    """

    def __init__(self, bridge: TelemetryBridge, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
        self.bridge = bridge
        self._init_ui()

        # Connect to TelemetryBridge signals
        self.bridge.snapshot_updated.connect(self._on_snapshot)

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)

        # 1. Top System Info Banner Card
        self.header_card = self._build_header_card()
        layout.addWidget(self.header_card)

        # 2. Row of Radial Gauges (CPU, Memory, GPU/Thermals)
        gauges_row = self._build_gauges_row()
        layout.addLayout(gauges_row)

        # 3. Middle Real-Time Telemetry Graph Card
        self.chart_card = self._build_chart_card()
        layout.addWidget(self.chart_card)

        # 4. Bottom Row: Storage & Network I/O + Top Processes
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)

        self.io_card = StorageNetworkCard(self)
        self.procs_card = TopProcessesPreview(self)

        bottom_row.addWidget(self.io_card, stretch=1)
        bottom_row.addWidget(self.procs_card, stretch=1)
        layout.addLayout(bottom_row)

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _build_header_card(self) -> QFrame:
        """Create the top system overview metadata badge."""
        card = QFrame(self)
        card.setProperty("class", "card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(20)

        # OS & Host
        col1 = QVBoxLayout()
        self.lbl_os = QLabel("OS: Detecting...")
        self.lbl_os.setStyleSheet("font-weight: 700; font-size: 13px; color: #F0F6FC;")
        self.lbl_cpu_model = QLabel("CPU: Detecting...")
        self.lbl_cpu_model.setStyleSheet("color: #90A4AE; font-size: 11px;")
        col1.addWidget(self.lbl_os)
        col1.addWidget(self.lbl_cpu_model)

        # Uptime & Memory Total
        col2 = QVBoxLayout()
        self.lbl_uptime = QLabel("Uptime: —")
        self.lbl_uptime.setStyleSheet(
            "color: #F0F6FC; font-size: 12px; font-weight: 600;"
        )
        self.lbl_mem_total = QLabel("Total RAM: —")
        self.lbl_mem_total.setStyleSheet("color: #90A4AE; font-size: 11px;")
        col2.addWidget(self.lbl_uptime)
        col2.addWidget(self.lbl_mem_total)

        card_layout.addLayout(col1, stretch=2)
        card_layout.addLayout(col2, stretch=1)
        return card

    def _build_gauges_row(self) -> QHBoxLayout:
        """Create the row of 3 circular telemetry gauges."""
        row = QHBoxLayout()
        row.setSpacing(16)

        # CPU Gauge Card
        self.cpu_gauge_card = QFrame(self)
        self.cpu_gauge_card.setProperty("class", "card")
        cpu_layout = QVBoxLayout(self.cpu_gauge_card)
        cpu_layout.setContentsMargins(10, 10, 10, 10)
        self.cpu_gauge = RadialGaugeWidget(
            title="CPU Load", unit="%", min_val=0, max_val=100
        )
        cpu_layout.addWidget(self.cpu_gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        # Memory Gauge Card
        self.mem_gauge_card = QFrame(self)
        self.mem_gauge_card.setProperty("class", "card")
        mem_layout = QVBoxLayout(self.mem_gauge_card)
        mem_layout.setContentsMargins(10, 10, 10, 10)
        self.mem_gauge = RadialGaugeWidget(
            title="Memory", unit="%", min_val=0, max_val=100
        )
        mem_layout.addWidget(self.mem_gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        # GPU / Thermals Gauge Card
        self.thermal_gauge_card = QFrame(self)
        self.thermal_gauge_card.setProperty("class", "card")
        thermal_layout = QVBoxLayout(self.thermal_gauge_card)
        thermal_layout.setContentsMargins(10, 10, 10, 10)
        self.thermal_gauge = RadialGaugeWidget(
            title="CPU Temp",
            unit="°C",
            min_val=0,
            max_val=105,
            threshold_warning=75.0,
            threshold_critical=90.0,
        )
        thermal_layout.addWidget(
            self.thermal_gauge, alignment=Qt.AlignmentFlag.AlignCenter
        )

        row.addWidget(self.cpu_gauge_card)
        row.addWidget(self.mem_gauge_card)
        row.addWidget(self.thermal_gauge_card)
        return row

    def _build_chart_card(self) -> QFrame:
        """Create the real-time telemetry history chart card."""
        card = QFrame(self)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("📈 REAL-TIME TELEMETRY STREAM (60s)")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #90A4AE;")
        layout.addWidget(title)

        self.chart = TimeSeriesChart(maxlen=60, parent=self)
        layout.addWidget(self.chart)
        return card

    def _on_snapshot(self, snapshot: Snapshot) -> None:
        """Process incoming telemetry snapshot and update all UI sub-components."""
        if not PYSIDE6_AVAILABLE or snapshot is None:
            return

        cpu_freq_mhz = 0.0
        ram_used_gb = 0.0
        ram_total_gb = 0.0

        for r in snapshot.readings:
            # CPU
            if r.metric == "cpu.utilization.total":
                self.cpu_gauge.set_value(r.value)
            elif r.metric == "cpu.frequency.current":
                cpu_freq_mhz = r.value / 1e6 if r.value > 1e4 else r.value
                self.cpu_gauge.set_value(
                    self.cpu_gauge.value, subtitle=f"{cpu_freq_mhz:.0f} MHz"
                )
            elif r.metric == "cpu.model":
                model_str = (
                    r.tags.get("model", "Generic CPU") if r.tags else "Generic CPU"
                )
                self.lbl_cpu_model.setText(f"CPU: {model_str}")

            # Memory
            elif r.metric == "memory.utilization":
                self.mem_gauge.set_value(r.value)
            elif r.metric == "memory.used_bytes":
                ram_used_gb = r.value / (1024.0**3)
            elif r.metric == "memory.total_bytes":
                ram_total_gb = r.value / (1024.0**3)
                self.lbl_mem_total.setText(f"Total RAM: {ram_total_gb:.1f} GB")

            # Thermals / GPU
            elif r.metric in ["thermal.cpu.temp", "thermal.cpu.package_temp"]:
                self.thermal_gauge.set_value(r.value, subtitle="Package")

            # System Info
            elif r.metric == "system.info.os_version":
                os_str = (
                    r.tags.get("os", "macOS / Windows") if r.tags else "macOS / Windows"
                )
                self.lbl_os.setText(f"OS: {os_str}")
            elif r.metric == "system.uptime":
                hours = int(r.value // 3600)
                mins = int((r.value % 3600) // 60)
                self.lbl_uptime.setText(f"Uptime: {hours}h {mins}m")

        if ram_used_gb > 0 and ram_total_gb > 0:
            self.mem_gauge.set_value(
                self.mem_gauge.value,
                subtitle=f"{ram_used_gb:.1f} / {ram_total_gb:.1f} GB",
            )

        # Update chart, I/O card, and top processes table
        self.chart.update_from_snapshot(snapshot)
        self.io_card.update_snapshot(snapshot)
        self.procs_card.update_snapshot(snapshot)
