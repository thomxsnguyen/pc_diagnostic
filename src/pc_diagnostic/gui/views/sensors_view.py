from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pc_diagnostic.gui.components import (
    FansVoltagesCard,
    PerCoreGridWidget,
    ThermalMatrixWidget,
)

if TYPE_CHECKING:
    from pc_diagnostic.gui.bridge import TelemetryBridge
    from pc_diagnostic.models import Snapshot

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class SensorsView(QWidget):
    """Hardware & Thermal Deep-Dive View featuring per-core CPU load grids,

    a multi-component thermal heatmap matrix, and fan/voltage rail monitors.
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
        scroll.setObjectName("sensors_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("sensors_root")
        main_vbox = QVBoxLayout(container)
        main_vbox.setContentsMargins(24, 20, 24, 24)
        main_vbox.setSpacing(16)

        # Sensor workspace
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)

        # Left Column
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        self.core_grid = PerCoreGridWidget(container)
        self.fans_volts_card = FansVoltagesCard(container)

        left_col.addWidget(self.core_grid)
        left_col.addWidget(self.fans_volts_card)
        left_col.addStretch()

        # Right Column
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        self.thermal_matrix = ThermalMatrixWidget(container)
        right_col.addWidget(self.thermal_matrix)

        columns_layout.addLayout(left_col, stretch=1)
        columns_layout.addLayout(right_col, stretch=1)

        main_vbox.addLayout(columns_layout)
        scroll.setWidget(container)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

    def _on_snapshot(self, snapshot: Snapshot) -> None:
        """Process incoming telemetry snapshot across sensor sub-components."""
        if not PYSIDE6_AVAILABLE or snapshot is None:
            return

        self.core_grid.update_snapshot(snapshot)
        self.thermal_matrix.update_snapshot(snapshot)
        self.fans_volts_card.update_snapshot(snapshot)
