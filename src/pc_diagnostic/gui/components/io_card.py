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
    if bytes_val < 1_000_000_000:
        return f"{bytes_val / 1_000_000:.0f} MB"
    return f"{bytes_val / 1_000_000_000:.1f} GB"


class StorageNetworkCard(QFrame):
    """Card widget displaying real-time Storage I/O throughput and Network Bandwidth."""

    def __init__(self, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setProperty("class", "card")
            self.setObjectName("overview_io_card")

        self._init_ui()

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Title
        title = QLabel("Storage & network")
        title.setObjectName("overview_section_title")
        layout.addWidget(title)

        subtitle = QLabel("Disk capacity and live transfer rates")
        subtitle.setObjectName("overview_section_subtitle")
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(12)

        # --- Storage Section ---
        lbl_storage_hdr = QLabel("Primary Disk")
        lbl_storage_hdr.setObjectName("overview_group_title")
        self.lbl_storage_used = QLabel("Used: 0 GB")
        self.lbl_storage_used.setObjectName("overview_detail_label")

        self.storage_bar = QProgressBar()
        self.storage_bar.setObjectName("overview_storage_bar")
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(0)

        storage_rates_layout = QHBoxLayout()
        self.lbl_disk_read = QLabel("Read: 0.0 MB/s")
        self.lbl_disk_read.setObjectName("overview_rate_secondary")
        self.lbl_disk_write = QLabel("Write: 0.0 MB/s")
        self.lbl_disk_write.setObjectName("overview_rate_primary")
        storage_rates_layout.addWidget(self.lbl_disk_read)
        storage_rates_layout.addWidget(self.lbl_disk_write)

        grid.addWidget(lbl_storage_hdr, 0, 0)
        grid.addWidget(self.lbl_storage_used, 0, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.storage_bar, 1, 0, 1, 2)
        grid.addLayout(storage_rates_layout, 2, 0, 1, 2)

        # Divider
        divider = QFrame()
        divider.setObjectName("overview_section_divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        grid.addWidget(divider, 3, 0, 1, 2)

        # --- Network Section ---
        lbl_net_hdr = QLabel("Network Bandwidth")
        lbl_net_hdr.setObjectName("overview_group_title")
        self.lbl_net_rates = QLabel("Active")
        self.lbl_net_rates.setObjectName("overview_detail_label")

        net_rates_layout = QHBoxLayout()
        self.lbl_net_rx = QLabel("Down: 0.0 KB/s")
        self.lbl_net_rx.setObjectName("overview_rate_secondary")
        self.lbl_net_tx = QLabel("Up: 0.0 KB/s")
        self.lbl_net_tx.setObjectName("overview_rate_primary")
        net_rates_layout.addWidget(self.lbl_net_rx)
        net_rates_layout.addWidget(self.lbl_net_tx)

        grid.addWidget(lbl_net_hdr, 4, 0)
        grid.addWidget(self.lbl_net_rates, 4, 1, Qt.AlignmentFlag.AlignRight)
        grid.addLayout(net_rates_layout, 5, 0, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()

    def update_snapshot(self, snapshot: Any) -> None:
        """Update storage and network counters from snapshot readings."""
        if (
            not PYSIDE6_AVAILABLE
            or snapshot is None
            or not hasattr(snapshot, "readings")
        ):
            return

        disk_usage: dict[str, dict[str, float]] = {}
        rates = {
            "disk_read": {"canonical": 0.0, "legacy": 0.0},
            "disk_write": {"canonical": 0.0, "legacy": 0.0},
            "net_recv": {"canonical": 0.0, "legacy": 0.0},
            "net_sent": {"canonical": 0.0, "legacy": 0.0},
        }
        seen: set[tuple[str, str]] = set()

        for r in snapshot.readings:
            if r.metric.startswith("disk.usage."):
                field = r.metric.removeprefix("disk.usage.")
                if field in {"used", "total", "percent"}:
                    mountpoint = (r.tags or {}).get("mountpoint", "")
                    disk_usage.setdefault(mountpoint, {})[field] = float(r.value)
            elif r.metric == "disk.used_bytes":
                disk_usage.setdefault("", {})["used"] = float(r.value)
            elif r.metric in {"disk.io.read_bytes", "disk.read_bytes_per_sec"}:
                source = "canonical" if r.metric == "disk.io.read_bytes" else "legacy"
                rates["disk_read"][source] += float(r.value)
                seen.add(("disk_read", source))
            elif r.metric in {"disk.io.write_bytes", "disk.write_bytes_per_sec"}:
                source = "canonical" if r.metric == "disk.io.write_bytes" else "legacy"
                rates["disk_write"][source] += float(r.value)
                seen.add(("disk_write", source))
            elif r.metric in {"network.io.bytes_recv", "network.rx_bytes_per_sec"}:
                source = (
                    "canonical" if r.metric == "network.io.bytes_recv" else "legacy"
                )
                rates["net_recv"][source] += float(r.value)
                seen.add(("net_recv", source))
            elif r.metric in {"network.io.bytes_sent", "network.tx_bytes_per_sec"}:
                source = (
                    "canonical" if r.metric == "network.io.bytes_sent" else "legacy"
                )
                rates["net_sent"][source] += float(r.value)
                seen.add(("net_sent", source))

        if disk_usage:
            # macOS splits its startup disk into a sealed system volume at `/`
            # and the writable user-data volume below. Display the latter as
            # the primary disk; other platforms continue to prefer `/`.
            usage = (
                disk_usage.get("/System/Volumes/Data")
                or disk_usage.get("/")
                or next(iter(disk_usage.values()))
            )
            used = usage.get("used", 0.0)
            total = usage.get("total", 0.0)
            if total > 0:
                self.lbl_storage_used.setText(
                    f"Used: {format_bytes_size(used)} / {format_bytes_size(total)}"
                )
                percent = usage.get("percent", (used / total) * 100.0)
                self.storage_bar.setValue(round(max(0.0, min(100.0, percent))))
            else:
                self.lbl_storage_used.setText(f"Used: {format_bytes_size(used)}")

        labels = (
            ("disk_read", self.lbl_disk_read, "Read"),
            ("disk_write", self.lbl_disk_write, "Write"),
            ("net_recv", self.lbl_net_rx, "Down"),
            ("net_sent", self.lbl_net_tx, "Up"),
        )
        for key, label, prefix in labels:
            source = "canonical" if (key, "canonical") in seen else "legacy"
            if (key, source) in seen:
                label.setText(f"{prefix}: {format_bytes_speed(rates[key][source])}")
