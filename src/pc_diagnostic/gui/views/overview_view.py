from __future__ import annotations

import json
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


def _display_cpu_name(value: Any) -> str:
    """Extract a compact processor name from plain text or hardware-profile JSON."""

    def find_name(payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in (
                "chip_type",
                "processor_name",
                "cpu_model",
                "model_name",
                "brand",
                "name",
            ):
                candidate = payload.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
            for candidate in payload.values():
                found = find_name(candidate)
                if found:
                    return found
        elif isinstance(payload, list):
            for candidate in payload:
                found = find_name(candidate)
                if found:
                    return found
        return None

    raw = str(value or "").strip()
    if not raw:
        return "Unknown CPU"

    name = raw
    if raw.startswith(("{", "[")):
        try:
            name = find_name(json.loads(raw)) or "Unknown CPU"
        except (json.JSONDecodeError, TypeError):
            name = raw.splitlines()[0]

    name = " ".join(name.split())
    return f"{name[:93]}…" if len(name) > 96 else name


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

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        container.setObjectName("overview_root")
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(20, 14, 20, 16)
        self.content_layout.setSpacing(12)

        # 1. Top System Info Banner Card
        self.header_card = self._build_header_card()
        self.content_layout.addWidget(self.header_card)

        # 2. Row of Radial Gauges (CPU, Memory, GPU/Thermals)
        gauges_row = self._build_gauges_row()
        self.content_layout.addLayout(gauges_row)

        # 3. Middle Real-Time Telemetry Graph Card
        self.chart_card = self._build_chart_card()
        self.content_layout.addWidget(self.chart_card)

        # 4. Bottom Row: Storage & Network I/O + Top Processes
        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.setSpacing(12)

        self.io_card = StorageNetworkCard(self)
        self.procs_card = TopProcessesPreview(self)

        self.bottom_layout.addWidget(self.io_card, stretch=1)
        self.bottom_layout.addWidget(self.procs_card, stretch=1)
        self.content_layout.addLayout(self.bottom_layout)

        self.scroll_area.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll_area)

    def _build_header_card(self) -> QFrame:
        """Create the top system overview metadata badge."""
        card = QFrame(self)
        card.setProperty("class", "card")
        card.setObjectName("overview_header")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(18)

        page_column = QVBoxLayout()
        page_column.setSpacing(4)
        page_title = QLabel("Overview")
        page_title.setObjectName("overview_page_title")
        page_subtitle = QLabel("Live system health and resource activity")
        page_subtitle.setObjectName("overview_page_subtitle")
        page_column.addWidget(page_title)
        page_column.addWidget(page_subtitle)
        card_layout.addLayout(page_column, stretch=2)

        divider = QFrame(card)
        divider.setObjectName("overview_header_divider")
        divider.setFrameShape(QFrame.Shape.VLine)
        card_layout.addWidget(divider)

        # OS & Host
        col1 = QVBoxLayout()
        col1.setSpacing(3)
        system_label = QLabel("SYSTEM")
        system_label.setObjectName("overview_meta_label")
        self.lbl_os = QLabel("Detecting…")
        self.lbl_os.setObjectName("overview_meta_primary")
        self.lbl_cpu_model = QLabel("Detecting processor…")
        self.lbl_cpu_model.setObjectName("overview_meta_secondary")
        col1.addWidget(system_label)
        col1.addWidget(self.lbl_os)
        col1.addWidget(self.lbl_cpu_model)

        # Uptime & Memory Total
        col2 = QVBoxLayout()
        col2.setSpacing(3)
        resources_label = QLabel("RESOURCES")
        resources_label.setObjectName("overview_meta_label")
        self.lbl_uptime = QLabel("Uptime —")
        self.lbl_uptime.setObjectName("overview_meta_primary")
        self.lbl_mem_total = QLabel("Memory —")
        self.lbl_mem_total.setObjectName("overview_meta_secondary")
        col2.addWidget(resources_label)
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
        self.cpu_gauge_card.setObjectName("overview_metric_card")
        cpu_layout = QVBoxLayout(self.cpu_gauge_card)
        cpu_layout.setContentsMargins(10, 10, 10, 10)
        self.cpu_gauge = RadialGaugeWidget(
            title="CPU Load", unit="%", min_val=0, max_val=100
        )
        cpu_layout.addWidget(self.cpu_gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        # Memory Gauge Card
        self.mem_gauge_card = QFrame(self)
        self.mem_gauge_card.setProperty("class", "card")
        self.mem_gauge_card.setObjectName("overview_metric_card")
        mem_layout = QVBoxLayout(self.mem_gauge_card)
        mem_layout.setContentsMargins(10, 10, 10, 10)
        self.mem_gauge = RadialGaugeWidget(
            title="Memory", unit="%", min_val=0, max_val=100
        )
        mem_layout.addWidget(self.mem_gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        # GPU / Thermals Gauge Card
        self.thermal_gauge_card = QFrame(self)
        self.thermal_gauge_card.setProperty("class", "card")
        self.thermal_gauge_card.setObjectName("overview_metric_card")
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

        row.addWidget(self.cpu_gauge_card, stretch=1)
        row.addWidget(self.mem_gauge_card, stretch=1)
        row.addWidget(self.thermal_gauge_card, stretch=1)
        return row

    def _build_chart_card(self) -> QFrame:
        """Create the real-time telemetry history chart card."""
        card = QFrame(self)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Performance history")
        title.setObjectName("overview_section_title")
        layout.addWidget(title)

        subtitle = QLabel("CPU, memory, disk, and network activity · Last 60 seconds")
        subtitle.setObjectName("overview_section_subtitle")
        layout.addWidget(subtitle)

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
            elif r.metric in ("system.info.cpu_model", "cpu.model"):
                model_str = "Generic CPU"
                if r.tags:
                    model_str = r.tags.get("value", r.tags.get("model", model_str))
                self.lbl_cpu_model.setText(_display_cpu_name(model_str))

            # Memory
            elif r.metric == "memory.utilization":
                self.mem_gauge.set_value(r.value)
            elif r.metric in ("memory.used", "memory.used_bytes"):
                ram_used_gb = r.value / (1024.0**3)
            elif r.metric in ("memory.total", "memory.total_bytes"):
                ram_total_gb = r.value / (1024.0**3)
                self.lbl_mem_total.setText(f"Memory {ram_total_gb:.1f} GB")

            # Thermals / GPU
            elif r.metric in [
                "thermal.cpu.temp",
                "thermal.cpu.package_temp",
                "system.temperature.cpu",
            ]:
                self.thermal_gauge.set_value(r.value, subtitle="CPU Die / Package")

            # System Info
            elif r.metric == "system.info.os_version":
                os_str = "Unknown OS"
                if r.tags:
                    os_str = r.tags.get("value", r.tags.get("os", os_str))
                self.lbl_os.setText(os_str.split(" (", 1)[0].strip())
            elif r.metric == "system.uptime":
                hours = int(r.value // 3600)
                mins = int((r.value % 3600) // 60)
                self.lbl_uptime.setText(f"Uptime {hours}h {mins}m")

        if ram_used_gb > 0 and ram_total_gb > 0:
            self.mem_gauge.set_value(
                self.mem_gauge.value,
                subtitle=f"{ram_used_gb:.1f} / {ram_total_gb:.1f} GB",
            )

        # Update chart, I/O card, and top processes table
        self.chart.update_from_snapshot(snapshot)
        self.io_card.update_snapshot(snapshot)
        self.procs_card.update_snapshot(snapshot)
