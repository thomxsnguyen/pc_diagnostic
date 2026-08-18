from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pc_diagnostic.cache import RollingCache

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QCheckBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class TimeSeriesChart(QWidget):
    """Hardware-accelerated 60-second real-time multi-line telemetry chart."""

    def __init__(
        self,
        maxlen: int = 60,
        parent: Any = None,
    ) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setMinimumHeight(200)

        self._maxlen = maxlen

        # Series buffers: metric_name -> (deque of values, color, is_visible, unit)
        self._series: dict[str, dict[str, Any]] = {
            "cpu.utilization.total": {
                "label": "CPU Load (%)",
                "color": QColor("#00E5FF") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
                "max_scale": 100.0,
            },
            "memory.utilization": {
                "label": "Memory (%)",
                "color": QColor("#7C4DFF") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
                "max_scale": 100.0,
            },
            "disk.read_bytes_per_sec": {
                "label": "Disk Read (MB/s)",
                "color": QColor("#00E676") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
                "max_scale": 100.0,
            },
            "network.rx_bytes_per_sec": {
                "label": "Net Down (MB/s)",
                "color": QColor("#FFD600") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
                "max_scale": 50.0,
            },
        }

        # Styling colors
        self._color_bg = QColor("#111622") if PYSIDE6_AVAILABLE else None
        self._color_grid = QColor("#1E2738") if PYSIDE6_AVAILABLE else None
        self._color_text = QColor("#607D8B") if PYSIDE6_AVAILABLE else None

    def add_point(self, metric: str, value: float) -> None:
        """Append a data point to a specific series buffer."""
        if metric in self._series:
            # Scale disk/net bytes to MB/s if needed
            if "bytes_per_sec" in metric:
                value = value / (1024.0 * 1024.0)
            self._series[metric]["values"].append(value)

    def update_from_snapshot(self, snapshot: Any) -> None:
        """Extract relevant metrics from latest Snapshot and update buffers."""
        if snapshot is None or not hasattr(snapshot, "readings"):
            return

        for r in snapshot.readings:
            if r.metric in self._series:
                self.add_point(r.metric, r.value)

        if PYSIDE6_AVAILABLE and hasattr(self, "update"):
            self.update()

    def set_series_visibility(self, metric: str, visible: bool) -> None:
        """Toggle visibility for a specific metric line."""
        if metric in self._series:
            self._series[metric]["visible"] = visible
            if PYSIDE6_AVAILABLE and hasattr(self, "update"):
                self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        if not PYSIDE6_AVAILABLE:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        width = float(self.width())
        height = float(self.height())
        padding_left = 40.0
        padding_right = 16.0
        padding_top = 28.0
        padding_bottom = 26.0

        plot_w = width - padding_left - padding_right
        plot_h = height - padding_top - padding_bottom

        if plot_w <= 10 or plot_h <= 10:
            painter.end()
            return

        # 1. Background Fill
        painter.fillRect(
            QRectF(padding_left, padding_top, plot_w, plot_h),
            self._color_bg,
        )

        # 2. Draw Grid Lines (Horizontal 0%, 25%, 50%, 75%, 100%)
        grid_pen = QPen(self._color_grid, 1.0, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)

        for step in [0.0, 0.25, 0.5, 0.75, 1.0]:
            y = padding_top + plot_h - (plot_h * step)
            painter.drawLine(QPointF(padding_left, y), QPointF(padding_left + plot_w, y))

            # Y-axis label
            painter.setPen(self._color_text)
            painter.drawText(
                QRectF(0, y - 7, padding_left - 6, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{int(step * 100)}%",
            )
            painter.setPen(grid_pen)

        # 3. Draw X-axis time marks (-60s, -45s, -30s, -15s, Now)
        time_labels = [("-60s", 0.0), ("-45s", 0.25), ("-30s", 0.5), ("-15s", 0.75), ("Now", 1.0)]
        painter.setPen(self._color_text)
        for lbl, ratio in time_labels:
            x = padding_left + (plot_w * ratio)
            painter.drawText(
                QRectF(x - 20, padding_top + plot_h + 6, 40, 16),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                lbl,
            )

        # 4. Draw Metric Lines
        for metric, info in self._series.items():
            if not info["visible"]:
                continue

            values = list(info["values"])
            if len(values) < 2:
                continue

            color = info["color"]
            pen = QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            path = QPainterPath()
            n_pts = len(values)
            step_x = plot_w / float(self._maxlen - 1)
            start_x_offset = plot_w - (float(n_pts - 1) * step_x)

            for i, val in enumerate(values):
                x = padding_left + start_x_offset + (float(i) * step_x)
                # Normalize value (clamp 0..100)
                norm = max(0.0, min(100.0, val)) / 100.0
                y = padding_top + plot_h - (plot_h * norm)

                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            painter.drawPath(path)

        # 5. Draw Legend (Top Right)
        legend_x = padding_left + 10
        painter.setFont(font)
        for metric, info in self._series.items():
            color = info["color"]
            label = info["label"]

            # Indicator dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(legend_x + 4, padding_top - 12), 4, 4)

            # Label text
            painter.setPen(self._color_text)
            painter.drawText(
                QRectF(legend_x + 12, padding_top - 20, 120, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            legend_x += 130

        painter.end()
