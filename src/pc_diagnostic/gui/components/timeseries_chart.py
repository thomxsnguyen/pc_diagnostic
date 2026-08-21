from __future__ import annotations

from collections import deque
from typing import Any, ClassVar

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class TimeSeriesChart(QWidget):
    """Hardware-accelerated 60-second real-time multi-line telemetry chart."""

    _THROUGHPUT_METRICS: ClassVar[tuple[str, str]] = (
        "disk.io.read_bytes",
        "network.io.bytes_recv",
    )
    _METRIC_ALIASES: ClassVar[dict[str, str]] = {
        "disk.read_bytes_per_sec": "disk.io.read_bytes",
        "network.rx_bytes_per_sec": "network.io.bytes_recv",
    }

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
                "color": QColor("#60A5FA") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
                "max_scale": 100.0,
            },
            "memory.utilization": {
                "label": "Memory (%)",
                "color": QColor("#A6ABB3") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
                "max_scale": 100.0,
            },
            "disk.io.read_bytes": {
                "label": "Disk Read (MB/s)",
                "color": QColor("#00E676") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
            },
            "network.io.bytes_recv": {
                "label": "Net Down (MB/s)",
                "color": QColor("#FFD600") if PYSIDE6_AVAILABLE else None,
                "values": deque(maxlen=maxlen),
                "visible": True,
            },
        }

        # Styling colors
        self._color_bg = QColor("#101114") if PYSIDE6_AVAILABLE else None
        self._color_grid = QColor("#24272D") if PYSIDE6_AVAILABLE else None
        self._color_text = QColor("#6F7680") if PYSIDE6_AVAILABLE else None

    def add_point(self, metric: str, value: float) -> None:
        """Append a data point to a specific series buffer."""
        metric = self._METRIC_ALIASES.get(metric, metric)
        if metric in self._series:
            if metric in self._THROUGHPUT_METRICS:
                value = value / (1024.0 * 1024.0)
            self._series[metric]["values"].append(value)

    def update_from_snapshot(self, snapshot: Any) -> None:
        """Extract relevant metrics from latest Snapshot and update buffers."""
        if snapshot is None or not hasattr(snapshot, "readings"):
            return

        canonical: dict[str, list[float]] = {
            metric: [] for metric in self._series
        }
        legacy: dict[str, list[float]] = {
            metric: [] for metric in self._series
        }
        for reading in snapshot.readings:
            metric = self._METRIC_ALIASES.get(reading.metric, reading.metric)
            if metric not in self._series:
                continue
            target = legacy if reading.metric in self._METRIC_ALIASES else canonical
            target[metric].append(float(reading.value))

        for metric in self._series:
            values = canonical[metric] or legacy[metric]
            if metric in self._THROUGHPUT_METRICS:
                self.add_point(metric, sum(values))
            elif values:
                self.add_point(metric, values[-1])

        if PYSIDE6_AVAILABLE and hasattr(self, "update"):
            self.update()

    def set_series_visibility(self, metric: str, visible: bool) -> None:
        """Toggle visibility for a specific metric line."""
        metric = self._METRIC_ALIASES.get(metric, metric)
        if metric in self._series:
            self._series[metric]["visible"] = visible
            if PYSIDE6_AVAILABLE and hasattr(self, "update"):
                self.update()

    def _throughput_scale(self) -> float:
        """Return one readable MB/s scale shared by disk and network series."""
        peak = max(
            (
                max(self._series[metric]["values"], default=0.0)
                for metric in self._THROUGHPUT_METRICS
            ),
            default=0.0,
        )
        return max(1.0, peak * 1.15)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        if not PYSIDE6_AVAILABLE:
            return

        assert self._color_bg is not None
        assert self._color_grid is not None
        assert self._color_text is not None
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        width = float(self.width())
        height = float(self.height())
        padding_left = 40.0
        padding_right = 58.0
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

        # 2. Draw Grid Lines with percent and throughput axes.
        grid_pen = QPen(self._color_grid, 1.0, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)

        throughput_scale = self._throughput_scale()
        for step in [0.0, 0.25, 0.5, 0.75, 1.0]:
            y = padding_top + plot_h - (plot_h * step)
            painter.drawLine(
                QPointF(padding_left, y), QPointF(padding_left + plot_w, y)
            )

            # Y-axis label
            painter.setPen(self._color_text)
            painter.drawText(
                QRectF(0, y - 7, padding_left - 6, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{int(step * 100)}%",
            )
            painter.drawText(
                QRectF(padding_left + plot_w + 6, y - 7, padding_right - 8, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{throughput_scale * step:.1f}",
            )
            painter.setPen(grid_pen)

        painter.setPen(self._color_text)
        painter.drawText(
            QRectF(
                padding_left + plot_w + 6,
                padding_top - 21,
                padding_right - 8,
                14,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "MB/s",
        )

        # 3. Draw X-axis time marks (-60s, -45s, -30s, -15s, Now)
        time_labels = [
            ("-60s", 0.0),
            ("-45s", 0.25),
            ("-30s", 0.5),
            ("-15s", 0.75),
            ("Now", 1.0),
        ]
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
            pen = QPen(
                color,
                2.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)

            path = QPainterPath()
            n_pts = len(values)
            step_x = plot_w / float(self._maxlen - 1)
            start_x_offset = plot_w - (float(n_pts - 1) * step_x)

            for i, val in enumerate(values):
                x = padding_left + start_x_offset + (float(i) * step_x)
                max_scale = (
                    throughput_scale
                    if metric in self._THROUGHPUT_METRICS
                    else info["max_scale"]
                )
                norm = max(0.0, min(max_scale, val)) / max_scale
                y = padding_top + plot_h - (plot_h * norm)

                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            painter.drawPath(path)

        # 5. Draw Legend (Top Right)
        legend_x = padding_left + 10
        painter.setFont(font)
        for _metric, info in self._series.items():
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
