"""Folder tree for browsing the disk; choosing a folder opens its photos."""

from __future__ import annotations

from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

from spektrafilm_gui.persistence import load_dialog_dir, save_dialog_dir
from spektrafilm_gui.theme_palette import ACCENT_FILL, SECTION_CARD_BG, TEXT_DIM
from spektrafilm_gui.ui_icons import ui_icon

Signal = QtCore.Signal
BRANCH_ICON_SIZE = 12
SELECTED_ROW_ALPHA = 46
LAST_FOLDER_KEY = 'browse_folder'
FOLDER_PANEL_WIDTH = 250
SELECTION_DELAY_MS = 180
REVEAL_SETTLE_MS = 150
REVEAL_EXPIRY_MS = 4000


class _FolderItemDelegate(QtWidgets.QStyledItemDelegate):
    """Highlights only the name cell; stylesheet selection also fills the indent area."""

    def paint(self, painter, option, index) -> None:
        state = QtWidgets.QStyle.StateFlag
        selected = bool(option.state & state.State_Selected)
        hovered = bool(option.state & state.State_MouseOver)
        if selected or hovered:
            color = QtGui.QColor(ACCENT_FILL if selected else SECTION_CARD_BG)
            if selected:
                color.setAlpha(SELECTED_ROW_ALPHA)
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QtCore.QRectF(option.rect).adjusted(0, 1, -1, -1), 4, 4)
            painter.restore()
        plain = QtWidgets.QStyleOptionViewItem(option)
        plain.state &= ~(state.State_Selected | state.State_MouseOver | state.State_HasFocus)
        super().paint(painter, plain, index)


class _FolderTree(QtWidgets.QTreeView):
    """Draws its own disclosure arrows; stylesheet branch images tile on selected rows."""

    def drawBranches(self, painter, rect, index) -> None:  # noqa: N802 - Qt API name
        if not self.model().hasChildren(index):
            return
        icon = ui_icon('chevron-down' if self.isExpanded(index) else 'chevron-right', TEXT_DIM)
        x = rect.right() - (self.indentation() + BRANCH_ICON_SIZE) // 2
        y = rect.center().y() - BRANCH_ICON_SIZE // 2
        icon.paint(painter, QtCore.QRect(x, y, BRANCH_ICON_SIZE, BRANCH_ICON_SIZE))


class FolderPanel(QtWidgets.QFrame):
    folder_chosen = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('folderPanel')
        self.setMinimumWidth(180)

        title = QtWidgets.QLabel('文件夹')
        title.setObjectName('stripTitle')

        self._model = QtWidgets.QFileSystemModel(self)
        self._model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.Drives)
        self._model.setRootPath('')

        self.tree = _FolderTree()
        self.tree.setObjectName('folderTree')
        self.tree.setModel(self._model)
        # The native Windows 11 style draws a selection pill at the far left of the row.
        self._tree_style = QtWidgets.QStyleFactory.create('Fusion')
        self.tree.setStyle(self._tree_style)
        self.tree.setItemDelegate(_FolderItemDelegate(self.tree))
        self.tree.setMouseTracking(True)
        self.tree.setHeaderHidden(True)
        for column in range(1, self._model.columnCount()):
            self.tree.hideColumn(column)
        self.tree.setIndentation(14)
        self.tree.setAnimated(False)
        # The name column fills the panel, so long names elide rather than scroll sideways.
        self.tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.tree.setTextElideMode(QtCore.Qt.ElideRight)
        self.tree.header().setStretchLastSection(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 8, 12)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self.tree, 1)

        # Debounced so arrowing through the tree does not open every folder on the way.
        self._pending_path = ''
        # Parent folders load and sort asynchronously, so scroll again once they settle.
        # The target expires so later manual expanding does not jump back to it.
        self._reveal_target = ''
        self._reveal_settle = QtCore.QTimer(self)
        self._reveal_settle.setSingleShot(True)
        self._reveal_settle.setInterval(REVEAL_SETTLE_MS)
        self._reveal_settle.timeout.connect(self._scroll_to_reveal_target)
        self._model.directoryLoaded.connect(lambda _path: self._reveal_settle.start())
        self._reveal_expiry = QtCore.QTimer(self)
        self._reveal_expiry.setSingleShot(True)
        self._reveal_expiry.setInterval(REVEAL_EXPIRY_MS)
        self._reveal_expiry.timeout.connect(self._clear_reveal_target)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SELECTION_DELAY_MS)
        self._timer.timeout.connect(self._emit_pending)
        self.tree.selectionModel().currentChanged.connect(self._on_current_changed)

    def reveal(self, path: str) -> None:
        """Select ``path`` in the tree, which also opens it."""
        index = self._model.index(path)
        if index.isValid():
            self._reveal_target = self._model.filePath(index)
            self.tree.setCurrentIndex(index)
            self._scroll_to_reveal_target()
            self._reveal_expiry.start()

    def restore_last_folder(self) -> None:
        last_folder = load_dialog_dir(LAST_FOLDER_KEY)
        if last_folder and Path(last_folder).is_dir():
            self.reveal(last_folder)

    def _scroll_to_reveal_target(self) -> None:
        if self._reveal_target:
            self.tree.scrollTo(self._model.index(self._reveal_target), QtWidgets.QAbstractItemView.PositionAtCenter)

    def _clear_reveal_target(self) -> None:
        self._reveal_target = ''

    def _on_current_changed(self, current: QtCore.QModelIndex, _previous: QtCore.QModelIndex) -> None:
        self._pending_path = self._model.filePath(current)
        if self._pending_path != self._reveal_target:
            self._reveal_target = ''
        self._timer.start()

    def _emit_pending(self) -> None:
        if self._pending_path and Path(self._pending_path).is_dir():
            save_dialog_dir(LAST_FOLDER_KEY, self._pending_path)
            self.folder_chosen.emit(self._pending_path)
