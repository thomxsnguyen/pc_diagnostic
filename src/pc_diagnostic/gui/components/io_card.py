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


def format_bytes_speed(bytes_val: float) -> str:
    """Format bytes/sec into human readable format."""
    if bytes_val < 1024:
        return f"{bytes_val:.0f} B/s"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB/s"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB/s"
    return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB/s"


def format_bytes_size(bytes_val: float) -> str:
    """Format bytes capacity into human readable format."""
    if bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.0f} MB"
    return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"


class StorageNetworkCard(QFrame):
    """Card widget displaying real-time Storage I/O throughput and Network Bandwidth."""

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setProperty("class", "card")

        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Title
        title = QLabel("STORAGE & NETWORK I/O")
        title.setProperty("class", "card_title")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #A6ABB3;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(12)

        # --- Storage Section ---
        lbl_storage_hdr = QLabel("Primary Disk")
        lbl_storage_hdr.setStyleSheet("font-weight: 700; color: #ECEEF1;")
        self.lbl_storage_used = QLabel("Used: 0 GB")
        self.lbl_storage_used.setStyleSheet("color: #A6ABB3; font-size: 11px;")

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(0)

        storage_rates_layout = QHBoxLayout()
        self.lbl_disk_read = QLabel("Read: 0.0 MB/s")
        self.lbl_disk_read.setStyleSheet(
            "color: #00E676; font-size: 12px; font-weight: 600;"
        )
        self.lbl_disk_write = QLabel("Write: 0.0 MB/s")
        self.lbl_disk_write.setStyleSheet(
            "color: #00B0FF; font-size: 12px; font-weight: 600;"
        )
        storage_rates_layout.addWidget(self.lbl_disk_read)
        storage_rates_layout.addWidget(self.lbl_disk_write)

        grid.addWidget(lbl_storage_hdr, 0, 0)
        grid.addWidget(self.lbl_storage_used, 0, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.storage_bar, 1, 0, 1, 2)
        grid.addLayout(storage_rates_layout, 2, 0, 1, 2)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #24272D; max-height: 1px;")
        grid.addWidget(divider, 3, 0, 1, 2)

        # --- Network Section ---
        lbl_net_hdr = QLabel("Network Bandwidth")
        lbl_net_hdr.setStyleSheet("font-weight: 700; color: #ECEEF1;")
        self.lbl_net_rates = QLabel("Active")
        self.lbl_net_rates.setStyleSheet("color: #A6ABB3; font-size: 11px;")

        net_rates_layout = QHBoxLayout()
        self.lbl_net_rx = QLabel("Down: 0.0 KB/s")
        self.lbl_net_rx.setStyleSheet(
            "color: #FFD600; font-size: 12px; font-weight: 600;"
        )
        self.lbl_net_tx = QLabel("Up: 0.0 KB/s")
        self.lbl_net_tx.setStyleSheet(
            "color: #FF9100; font-size: 12px; font-weight: 600;"
        )
        net_rates_layout.addWidget(self.lbl_net_rx)
        net_rates_layout.addWidget(self.lbl_net_tx)

        grid.addWidget(lbl_net_hdr, 4, 0)
        grid.addWidget(self.lbl_net_rates, 4, 1, Qt.AlignmentFlag.AlignRight)
        grid.addLayout(net_rates_layout, 5, 0, 1, 2)

        layout.addLayout(grid)

    def update_snapshot(self, snapshot: Any) -> None:
        """Update storage and network counters from snapshot readings."""
        if (
            not PYSIDE6_AVAILABLE
            or snapshot is None
            or not hasattr(snapshot, "readings")
        ):
            return

        for r in snapshot.readings:
            if r.metric == "disk.used_bytes":
                self.lbl_storage_used.setText(f"Used: {format_bytes_size(r.value)}")
            elif r.metric == "disk.read_bytes_per_sec":
                self.lbl_disk_read.setText(f"Read: {format_bytes_speed(r.value)}")
            elif r.metric == "disk.write_bytes_per_sec":
                self.lbl_disk_write.setText(f"Write: {format_bytes_speed(r.value)}")
            elif r.metric == "network.rx_bytes_per_sec":
                self.lbl_net_rx.setText(f"Down: {format_bytes_speed(r.value)}")
            elif r.metric == "network.tx_bytes_per_sec":
                self.lbl_net_tx.setText(f"Up: {format_bytes_speed(r.value)}")
