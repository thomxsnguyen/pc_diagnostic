from __future__ import annotations

from typing import override

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSize
from PySide6.QtWidgets import (
    QComboBox,
    QListView,
    QStyledItemDelegate,
    QStyleFactory,
    QStyleOptionViewItem,
    QWidget,
)


class _CompactItemDelegate(QStyledItemDelegate):
    """Keep combo popup rows compact and consistent across platforms."""

    @override
    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        size = super().sizeHint(option, index)
        size.setHeight(30)
        return size


class ProfessionalComboBox(QComboBox):
    """Application-styled combo box that avoids oversized native popups."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # macOS otherwise renders this popup as an oversized native menu.
        self._popup_style = QStyleFactory.create("Fusion")
        if self._popup_style is not None:
            self.setStyle(self._popup_style)

        popup = QListView(self)
        popup.setUniformItemSizes(True)
        popup.setSpacing(0)
        popup.setItemDelegate(_CompactItemDelegate(popup))
        self.setView(popup)
        self.setMaxVisibleItems(8)
