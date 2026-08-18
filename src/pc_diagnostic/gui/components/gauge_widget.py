from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class RadialGaugeWidget(QWidget):
    """Hardware-accelerated circular radial gauge for displaying real-time telemetry."""

    def __init__(
        self,
        title: str = "CPU",
        unit: str = "%",
        min_val: float = 0.0,
        max_val: float = 100.0,
        threshold_warning: float = 55.0,
        threshold_critical: float = 80.0,
        parent: Any = None,
    ) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
            self.setMinimumSize(160, 160)

        self._title = title
        self._unit = unit
        self._min_val = min_val
        self._max_val = max_val
        self._value = 0.0
        self._subtitle = ""
        self._threshold_warning = threshold_warning
        self._threshold_critical = threshold_critical

        # Colors
        self._color_track = QColor("#1C2536") if PYSIDE6_AVAILABLE else None
        self._color_normal = QColor("#00E676") if PYSIDE6_AVAILABLE else None
        self._color_warning = QColor("#FFD600") if PYSIDE6_AVAILABLE else None
        self._color_critical = QColor("#FF1744") if PYSIDE6_AVAILABLE else None
        self._color_text = QColor("#F0F6FC") if PYSIDE6_AVAILABLE else None
        self._color_subtitle = QColor("#90A4AE") if PYSIDE6_AVAILABLE else None

    @property
    def value(self) -> float:
        return self._value

    @property
    def title(self) -> str:
        return self._title

    def set_value(self, val: float, subtitle: str | None = None) -> None:
        """Update gauge value and optional subtitle, triggering a repaint."""
        self._value = max(self._min_val, min(self._max_val, val))
        if subtitle is not None:
            self._subtitle = subtitle
        if PYSIDE6_AVAILABLE and hasattr(self, "update"):
            self.update()

    def set_theme_colors(
        self,
        track: str,
        normal: str,
        warning: str,
        critical: str,
        text: str,
        subtitle: str,
    ) -> None:
        """Update gauge color palette to match the active theme."""
        if not PYSIDE6_AVAILABLE:
            return
        self._color_track = QColor(track)
        self._color_normal = QColor(normal)
        self._color_warning = QColor(warning)
        self._color_critical = QColor(critical)
        self._color_text = QColor(text)
        self._color_subtitle = QColor(subtitle)
        self.update()

    def _get_active_color(self) -> Any:
        if self._value >= self._threshold_critical:
            return self._color_critical
        elif self._value >= self._threshold_warning:
            return self._color_warning
        return self._color_normal

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        if not PYSIDE6_AVAILABLE:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        width = float(self.width())
        height = float(self.height())
        size = min(width, height)
        pen_width = 11.0
        radius = (size / 2.0) - (pen_width * 1.5)

        center_x = width / 2.0
        center_y = (height / 2.0) + 4.0

        rect = QRectF(
            center_x - radius,
            center_y - radius,
            radius * 2.0,
            radius * 2.0,
        )

        start_angle = 210.0
        total_span = 240.0

        # 1. Draw Background Track Arc
        track_pen = QPen(self._color_track, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect, int(start_angle * 16), int(-total_span * 16))

        # 2. Draw Active Value Arc
        norm_val = (self._value - self._min_val) / (self._max_val - self._min_val) if self._max_val > self._min_val else 0.0
        value_span = total_span * norm_val
        if value_span > 0.1:
            active_pen = QPen(
                self._get_active_color(),
                pen_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
            painter.setPen(active_pen)
            painter.drawArc(rect, int(start_angle * 16), int(-value_span * 16))

        # 3. Draw Title (Top)
        painter.setPen(self._color_subtitle)
        title_font = QFont(self.font())
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(0, center_y - radius - 14, width, 18),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._title.upper(),
        )

        # 4. Draw Center Value
        painter.setPen(self._color_text)
        val_font = QFont(self.font())
        val_font.setPointSize(20)
        val_font.setBold(True)
        painter.setFont(val_font)
        val_str = f"{self._value:.0f}{self._unit}" if self._unit == "%" else f"{self._value:.1f}{self._unit}"
        painter.drawText(
            QRectF(0, center_y - 14, width, 30),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            val_str,
        )

        # 5. Draw Subtitle (Bottom)
        if self._subtitle:
            painter.setPen(self._color_subtitle)
            sub_font = QFont(self.font())
            sub_font.setPointSize(9)
            sub_font.setBold(False)
            painter.setFont(sub_font)
            painter.drawText(
                QRectF(0, center_y + 14, width, 20),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                self._subtitle,
            )

        painter.end()
