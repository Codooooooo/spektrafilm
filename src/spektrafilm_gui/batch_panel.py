"""Film strip / contact sheet of imported photos, plus the batch export dialog."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from spektrafilm_gui.persistence import load_dialog_dir, save_dialog_dir
from spektrafilm_gui.theme_palette import SURFACE_INPUT, TEXT_MAIN, TEXT_ON_ACCENT
from spektrafilm_gui.ui_icons import ui_icon

Qt = QtCore.Qt
Signal = QtCore.Signal

STRIP_ICON_SIZE = QtCore.QSize(148, 100)
STRIP_CELL_SIZE = QtCore.QSize(164, 128)
GRID_ICON_SIZE = QtCore.QSize(270, 190)
GRID_CELL_SIZE = QtCore.QSize(292, 232)
STRIP_HEIGHT = 196
QWIDGETSIZE_MAX = 16777215
FAILED_PREFIX = '⚠ '
PATH_ROLE = int(Qt.UserRole)
EXPORT_FORMATS = (
    ('JPEG（8 位）', '.jpg'),
    ('TIFF（16 位）', '.tif'),
    ('PNG（8 位）', '.png'),
    ('EXR（16 位浮点）', '.exr'),
)
PHOTO_FILE_FILTER = (
    '照片 (*.jpg *.jpeg *.png *.tif *.tiff *.exr *.dng *.cr2 *.cr3 *.nef *.nrw *.arw *.srf *.sr2 '
    '*.raf *.rw2 *.orf *.pef *.srw *.x3f *.3fr *.iiq);;所有文件 (*)'
)


def _pixmap_from_rgb(image: np.ndarray) -> QtGui.QPixmap:
    height, width = image.shape[:2]
    buffer = np.ascontiguousarray(image[..., :3], dtype=np.uint8)
    qimage = QtGui.QImage(buffer.data, width, height, 3 * width, QtGui.QImage.Format.Format_RGB888)
    return QtGui.QPixmap.fromImage(qimage.copy())


def _placeholder_pixmap() -> QtGui.QPixmap:
    pixmap = QtGui.QPixmap(STRIP_ICON_SIZE)
    pixmap.fill(QtGui.QColor(SURFACE_INPUT))
    return pixmap


def _tool_button(text: str, icon_name: str, tooltip: str, *, role: str = 'toolAction', icon_color: str = TEXT_MAIN) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setIcon(ui_icon(icon_name, icon_color))
    button.setIconSize(QtCore.QSize(16, 16))
    button.setToolTip(tooltip)
    button.setProperty('role', role)
    button.setCursor(Qt.PointingHandCursor)
    return button


class BatchStrip(QtWidgets.QFrame):
    add_requested = Signal()
    files_dropped = Signal(list)
    item_selected = Signal(int)
    remove_requested = Signal(int)
    clear_requested = Signal()
    preview_requested = Signal()
    export_requested = Signal()
    cancel_requested = Signal()
    grid_toggled = Signal(bool)
    format_filter_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('batchStrip')
        self.setAcceptDrops(True)
        self.setFixedHeight(STRIP_HEIGHT)

        self.title = QtWidgets.QLabel('照片')
        self.title.setObjectName('stripTitle')
        self.add_button = _tool_button('添加', 'plus', '添加多张照片，支持 RAW、JPEG、TIFF、PNG、EXR，也可以直接拖到这里')
        self.grid_button = _tool_button('', 'grid', '在胶片条和大图网格之间切换')
        self.grid_button.setCheckable(True)
        self.clear_button = _tool_button('', 'trash', '清空列表（不会删除硬盘上的文件）')
        self.preview_button = _tool_button('批量预览', 'eye', '用当前胶片和参数快速生成所有照片的预览')
        self.export_button = _tool_button(
            '批量输出', 'export', '用当前胶片和参数输出所有照片的全分辨率文件',
            role='primaryTool', icon_color=TEXT_ON_ACCENT,
        )
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(180)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        self.progress_label = QtWidgets.QLabel('')
        self.progress_label.setObjectName('stripProgress')
        self.progress_label.hide()
        self.cancel_button = _tool_button('取消', 'close', '当前这张处理完后停止')
        self.cancel_button.hide()

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self.title)
        header.addSpacing(6)
        header.addWidget(self.add_button)
        header.addWidget(self.grid_button)
        header.addWidget(self.clear_button)
        header.addSpacing(10)
        self._format_row = QtWidgets.QHBoxLayout()
        self._format_row.setSpacing(4)
        self._format_chips: dict[str, QtWidgets.QPushButton] = {}
        header.addLayout(self._format_row)
        header.addStretch(1)
        header.addWidget(self.progress_label)
        header.addWidget(self.progress)
        header.addWidget(self.cancel_button)
        header.addSpacing(6)
        header.addWidget(self.preview_button)
        header.addWidget(self.export_button)

        self.list = QtWidgets.QListWidget()
        self.list.setObjectName('filmStrip')
        self.list.setAcceptDrops(False)
        self.list.setViewMode(QtWidgets.QListView.IconMode)
        self.list.setMovement(QtWidgets.QListView.Static)
        self.list.setResizeMode(QtWidgets.QListView.Adjust)
        self.list.setLayoutMode(QtWidgets.QListView.Batched)
        self.list.setBatchSize(200)
        self.list.setTextElideMode(Qt.ElideMiddle)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list.currentRowChanged.connect(self._on_current_row_changed)
        self.list.customContextMenuRequested.connect(self._show_context_menu)

        self.empty_hint = QtWidgets.QLabel('把照片拖到这里，或点击“添加”。可以一次选择多张。')
        self.empty_hint.setObjectName('stripEmpty')
        self.empty_hint.setAlignment(Qt.AlignCenter)

        self._stack = QtWidgets.QStackedLayout()
        self._stack.addWidget(self.empty_hint)
        self._stack.addWidget(self.list)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addLayout(self._stack, 1)

        self.add_button.clicked.connect(self.add_requested.emit)
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self.preview_button.clicked.connect(self.preview_requested.emit)
        self.export_button.clicked.connect(self.export_requested.emit)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.grid_button.toggled.connect(self._set_grid_mode)
        self._set_grid_mode(False)
        self._refresh_header()

    def is_grid_mode(self) -> bool:
        return self.grid_button.isChecked()

    def add_items(self, paths: list[str]) -> None:
        placeholder = QtGui.QIcon(_placeholder_pixmap())
        self.list.setUpdatesEnabled(False)
        for path in paths:
            item = QtWidgets.QListWidgetItem(placeholder, Path(path).name)
            item.setData(PATH_ROLE, path)
            item.setToolTip(path)
            self.list.addItem(item)
        self.list.setUpdatesEnabled(True)
        self._refresh_header()

    def set_thumbnail(self, index: int, image: np.ndarray) -> None:
        item = self.list.item(index)
        if item is not None:
            item.setIcon(QtGui.QIcon(_pixmap_from_rgb(image)))

    def set_format_counts(self, counts: dict[str, int], active: str) -> None:
        """Show a filter chip per format present; a single format needs no filter."""
        while self._format_row.count():
            widget = self._format_row.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)  # deleteLater alone leaves it on screen until the next event loop pass
                widget.deleteLater()
        self._format_chips.clear()
        if len(counts) < 2:
            return
        total = sum(counts.values())
        for group, label, count in [('', '全部', total), *((name, name, number) for name, number in counts.items())]:
            chip = QtWidgets.QPushButton(f'{label} {count}')
            chip.setCheckable(True)
            chip.setChecked(group == active)
            chip.setProperty('role', 'chip')
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip(f'只显示 {label} 格式的照片，批量预览和输出也只处理这些照片' if group else '显示所有格式')
            chip.clicked.connect(lambda _checked=False, name=group: self.format_filter_changed.emit(name))
            self._format_row.addWidget(chip)
            self._format_chips[group] = chip

    def set_row_hidden(self, index: int, hidden: bool) -> None:
        item = self.list.item(index)
        if item is not None:
            item.setHidden(hidden)

    def set_visible_count(self, visible: int, total: int) -> None:
        if not total:
            self.title.setText('照片')
        else:
            self.title.setText(f'照片  {visible}' if visible == total else f'照片  {visible} / {total}')

    def mark_failed(self, index: int) -> None:
        item = self.list.item(index)
        if item is not None and not item.text().startswith(FAILED_PREFIX):
            item.setText(f'{FAILED_PREFIX}{item.text()}')
            item.setToolTip(f'无法打开这张照片\n{item.data(PATH_ROLE)}')

    def take_item(self, index: int) -> None:
        self.list.takeItem(index)
        self._refresh_header()

    def clear_items(self) -> None:
        self.list.clear()
        self._refresh_header()

    def set_current(self, index: int) -> None:
        was_blocked = self.list.blockSignals(True)
        self.list.setCurrentRow(index)
        self.list.blockSignals(was_blocked)

    def set_running(self, running: bool) -> None:
        self.progress.setVisible(running)
        self.progress_label.setVisible(running)
        self.cancel_button.setVisible(running)
        self.preview_button.setEnabled(not running)
        self.export_button.setEnabled(not running)
        self.clear_button.setEnabled(not running)
        self.add_button.setEnabled(not running)
        if running:
            self.progress.setValue(0)
            self.progress_label.setText('准备中……')

    def set_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.progress_label.setText(f'{done} / {total}')

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API name
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def _refresh_header(self) -> None:
        count = self.list.count()
        self.title.setText(f'照片  {count}' if count else '照片')
        self._stack.setCurrentWidget(self.list if count else self.empty_hint)

    def _on_current_row_changed(self, row: int) -> None:
        if row >= 0:
            self.item_selected.emit(row)

    def _show_context_menu(self, position: QtCore.QPoint) -> None:
        item = self.list.itemAt(position)
        if item is None:
            return
        menu = QtWidgets.QMenu(self)
        remove_action = menu.addAction('从列表移除')
        if menu.exec(self.list.viewport().mapToGlobal(position)) == remove_action:
            self.remove_requested.emit(self.list.row(item))

    def _set_grid_mode(self, enabled: bool) -> None:
        self.list.setIconSize(GRID_ICON_SIZE if enabled else STRIP_ICON_SIZE)
        self.list.setGridSize(GRID_CELL_SIZE if enabled else STRIP_CELL_SIZE)
        self.list.setWrapping(enabled)
        self.list.setFlow(QtWidgets.QListView.LeftToRight)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff if enabled else Qt.ScrollBarAsNeeded)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if enabled else Qt.ScrollBarAlwaysOff)
        # Uniform sizes make per-thumbnail updates cheap, but the cached size must be dropped here.
        self.list.setUniformItemSizes(False)
        self.list.doItemsLayout()
        self.list.setUniformItemSizes(True)
        if enabled:
            self.setMinimumHeight(0)
            self.setMaximumHeight(QWIDGETSIZE_MAX)
        else:
            self.setFixedHeight(STRIP_HEIGHT)
        self.grid_toggled.emit(enabled)


class BatchExportDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, photo_count: int) -> None:
        super().__init__(parent)
        self.setWindowTitle('批量输出')
        self.setMinimumWidth(480)
        self.setObjectName('batchExportDialog')

        heading = QtWidgets.QLabel(f'输出 {photo_count} 张照片')
        heading.setObjectName('dialogHeading')
        note = QtWidgets.QLabel('使用当前的胶片和全部参数，按全分辨率处理。每张可能需要几十秒，已有文件不会被覆盖。')
        note.setObjectName('dialogNote')
        note.setWordWrap(True)

        self.directory = QtWidgets.QLineEdit(load_dialog_dir('batch_export') or str(Path.home() / 'Pictures'))
        browse = QtWidgets.QPushButton('选择')
        browse.setProperty('role', 'compactAction')
        browse.clicked.connect(self._browse)
        directory_row = QtWidgets.QHBoxLayout()
        directory_row.setSpacing(6)
        directory_row.addWidget(self.directory, 1)
        directory_row.addWidget(browse)

        self.format = QtWidgets.QComboBox()
        for label, extension in EXPORT_FORMATS:
            self.format.addItem(label, extension)
        self.suffix = QtWidgets.QLineEdit('_film')

        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addRow('输出文件夹', directory_row)
        form.addRow('文件格式', self.format)
        form.addRow('文件名后缀', self.suffix)

        buttons = QtWidgets.QDialogButtonBox()
        start = buttons.addButton('开始输出', QtWidgets.QDialogButtonBox.AcceptRole)
        start.setProperty('role', 'primaryTool')
        buttons.addButton('取消', QtWidgets.QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(heading)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def directory_value(self) -> str:
        return self.directory.text().strip()

    def extension_value(self) -> str:
        return str(self.format.currentData())

    def suffix_value(self) -> str:
        return self.suffix.text().strip()

    def remember_directory(self) -> None:
        save_dialog_dir('batch_export', self.directory_value())

    def _browse(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, '选择输出文件夹', self.directory_value())
        if chosen:
            self.directory.setText(chosen)
