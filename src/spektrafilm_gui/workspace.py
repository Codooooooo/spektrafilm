"""Desktop shell around the viewer and controls: header, film strip, icon toolbar."""

from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

from spektrafilm_gui.batch_panel import BatchStrip
from spektrafilm_gui.controller_batch import BatchController
from spektrafilm_gui.editing_tools import EditHistory, ViewerActions, refresh_slider_defaults, reset_look_to_defaults
from spektrafilm_gui.folder_panel import FOLDER_PANEL_WIDTH, FolderPanel
from spektrafilm_gui.napari_layout import APP_ICON_PATH
from spektrafilm_gui.stock_picker import StockSelector, stock_info
from spektrafilm_gui.theme_palette import TEXT_DIM, TEXT_MAIN
from spektrafilm_gui.ui_icons import ui_icon
from spektrafilm_gui.widget_primitives import CollapsibleSection

Qt = QtCore.Qt
HEADER_LOGO_SIZE = 26
TAB_ICONS = ('sliders', 'film', 'photo', 'prism', 'settings')
VIEWER_TOOL_ICONS = {
    'rotateCcwButton': ('rotate-ccw', '逆时针旋转 90°'),
    'rotateCwButton': ('rotate-cw', '顺时针旋转 90°'),
    'homeViewButton': ('fit', '重置视图，让照片完整显示'),
}


class _Header(QtWidgets.QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('appHeader')

        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QIcon(str(APP_ICON_PATH)).pixmap(HEADER_LOGO_SIZE, HEADER_LOGO_SIZE))
        wordmark = QtWidgets.QLabel('spektrafilm')
        wordmark.setObjectName('wordmark')

        self.file_name = QtWidgets.QLabel('')
        self.file_name.setObjectName('headerFile')
        self.file_name.setAlignment(Qt.AlignCenter)

        self.folder_toggle = self._tool_button('', 'folder', '显示或隐藏文件夹面板')
        self.folder_toggle.setCheckable(True)
        self.folder_toggle.setChecked(True)
        self.open_folder_button = self._tool_button('打开文件夹', 'folder', '打开一个文件夹，直接浏览和编辑里面的照片')
        self.import_button = self._tool_button('导入照片', 'plus', '添加单独的几张照片到当前列表')

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 12, 8)
        layout.setSpacing(10)
        layout.addWidget(logo)
        layout.addWidget(wordmark)
        layout.addSpacing(10)
        layout.addWidget(self.folder_toggle)
        layout.addStretch(1)
        layout.addWidget(self.file_name)
        layout.addStretch(1)
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.import_button)

    @staticmethod
    def _tool_button(text: str, icon_name: str, tooltip: str) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setProperty('role', 'toolAction')
        button.setIcon(ui_icon(icon_name, TEXT_MAIN))
        button.setIconSize(QtCore.QSize(16, 16))
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def show_current(self, name: str, position: int, total: int) -> None:
        self.file_name.setText(f'{name}    {position} / {total}' if name else '')


def _wrap_with_header(main_window: QtWidgets.QMainWindow, header: QtWidgets.QWidget) -> None:
    body = main_window.takeCentralWidget()
    shell = QtWidgets.QWidget()
    shell.setObjectName('appCentral')
    layout = QtWidgets.QVBoxLayout(shell)
    layout.setContentsMargins(8, 8, 8, 0)
    layout.setSpacing(0)
    layout.addWidget(header)
    layout.addWidget(body, 1)
    main_window.setCentralWidget(shell)


def _set_role(widget: QtWidgets.QWidget, role: str) -> None:
    """Change a style role on an already polished widget."""
    widget.setProperty('role', role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _dress_viewer_toolbar(main_window: QtWidgets.QMainWindow) -> None:
    for object_name, (icon_name, tooltip) in VIEWER_TOOL_ICONS.items():
        button = main_window.findChild(QtWidgets.QPushButton, object_name)
        if button is not None:
            button.setText('')
            button.setIcon(ui_icon(icon_name, TEXT_MAIN))
            button.setIconSize(QtCore.QSize(18, 18))
            button.setToolTip(tooltip)
            _set_role(button, 'iconAction')
    for object_name in ('zoom100Button', 'zoom200Button', 'zoom400Button'):
        button = main_window.findChild(QtWidgets.QPushButton, object_name)
        if button is not None:
            _set_role(button, 'iconAction')


def _dress_tabs(main_window: QtWidgets.QMainWindow) -> None:
    tabs = main_window.findChild(QtWidgets.QTabWidget, 'controlsTabWidget')
    if tabs is None:
        return
    tabs.setIconSize(QtCore.QSize(16, 16))
    for index, icon_name in enumerate(TAB_ICONS[:tabs.count()]):
        tabs.setTabIcon(index, ui_icon(icon_name, TEXT_DIM))


def _reorder_main_tab(widgets: Any) -> None:
    """Put what is adjusted most at the top; imports move to the header and strip."""
    layout = widgets.simulation.parentWidget().layout()
    ordered = (
        widgets.simulation,
        widgets.exposure_control,
        widgets.enlarger,
        widgets.camera,
        widgets.scanner,
        widgets.load_raw,
        widgets.input_image,
        widgets.preview_crop,
        widgets.output,
    )
    for section in ordered:
        layout.removeWidget(section)
    for position, section in enumerate(ordered):
        layout.insertWidget(position, section)
    widgets.filepicker.hide()


def _attach_strip(main_window: QtWidgets.QMainWindow, strip: BatchStrip) -> None:
    panel = main_window.findChild(QtWidgets.QFrame, 'viewerPanel')
    layout = panel.layout()
    viewer_item = layout.itemAt(0).widget()
    toolbar = layout.itemAt(layout.count() - 1).widget()
    layout.addSpacing(8)
    layout.addWidget(strip)

    def set_grid_mode(enabled: bool) -> None:
        viewer_item.setVisible(not enabled)
        toolbar.setVisible(not enabled)
        layout.setStretchFactor(strip, 1 if enabled else 0)

    strip.grid_toggled.connect(set_grid_mode)


def _attach_folder_panel(main_window: QtWidgets.QMainWindow, folders: FolderPanel) -> None:
    splitter = main_window.findChild(QtWidgets.QFrame, 'viewerPanel').parentWidget()
    viewer_width, controls_width = splitter.sizes()
    splitter.insertWidget(0, folders)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setStretchFactor(2, 0)
    splitter.setSizes([FOLDER_PANEL_WIDTH, max(viewer_width - FOLDER_PANEL_WIDTH, 1), controls_width])


def _install_stock_selectors(widgets: Any, gui: Any) -> tuple[StockSelector, StockSelector]:
    simulation = widgets.simulation
    form = simulation.film_stock.parentWidget().layout()
    for combo in (simulation.film_stock, simulation.print_paper):
        form.setRowVisible(combo, False)
    film = StockSelector(kind='film', heading='胶片', combo=simulation.film_stock, widgets=widgets, gui=gui)
    paper = StockSelector(kind='print', heading='相纸', combo=simulation.print_paper, widgets=widgets, gui=gui)
    form.insertRow(0, film.card)
    form.insertRow(1, paper.card)

    def sync_paper_context(*_args) -> None:
        info = stock_info(film.current_value())
        paper.set_context(note='反转片直接观看，相纸不起作用' if info.is_positive else '', recommended=info.target_print)

    film.changed.connect(sync_paper_context)
    sync_paper_context()
    return film, paper


def _install_compare_button(main_window: QtWidgets.QMainWindow, actions: ViewerActions) -> QtWidgets.QPushButton:
    anchor = main_window.findChild(QtWidgets.QPushButton, 'rotateCcwButton')
    layout = anchor.parentWidget().layout()
    button = QtWidgets.QPushButton()
    button.setCheckable(True)
    button.setIcon(ui_icon('compare', TEXT_MAIN))
    button.setIconSize(QtCore.QSize(18, 18))
    button.setToolTip('对比原图（快捷键 \\）')
    button.setProperty('role', 'iconAction')
    button.setFixedHeight(anchor.height())
    button.toggled.connect(actions.set_comparing)
    layout.insertWidget(layout.indexOf(anchor), button)
    return button


def _install_reset_button(widgets: Any, viewer: Any) -> None:
    button = QtWidgets.QPushButton('重置')
    button.setProperty('role', 'toolAction')
    button.setToolTip('恢复当前胶片和相纸的默认参数，可以撤销')
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(lambda: reset_look_to_defaults(widgets=widgets, viewer=viewer))
    widgets.simulation.bottom_bar.layout().itemAt(0).layout().addWidget(button)


def _remember_section_states(main_window: QtWidgets.QMainWindow) -> None:
    """Panels reopen the way they were left."""
    settings = QtCore.QSettings('spektrafilm', 'spektrafilm')
    for index, section in enumerate(main_window.findChildren(CollapsibleSection)):
        key = f'sections/{index}'
        stored = settings.value(key)
        if stored is not None:
            section._toggle.setChecked(str(stored).lower() == 'true')  # pylint: disable=protected-access
        section._toggle.toggled.connect(  # pylint: disable=protected-access
            lambda expanded, name=key: QtCore.QSettings('spektrafilm', 'spektrafilm').setValue(name, expanded),
        )


def _install_shortcuts(main_window: QtWidgets.QMainWindow, bindings: dict[str, Any]) -> None:
    for sequence, handler in bindings.items():
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), main_window)
        shortcut.activated.connect(handler)


def install_workspace(app: Any) -> BatchController:
    main_window = app.main_window
    header = _Header()
    strip = BatchStrip()
    folders = FolderPanel()
    batch = BatchController(viewer=app.viewer, widgets=app.widgets, gui_controller=app.controller, strip=strip)
    header.import_button.clicked.connect(batch.choose_files)
    header.folder_toggle.toggled.connect(folders.setVisible)
    batch.current_changed.connect(header.show_current)
    folders.folder_chosen.connect(batch.open_folder)
    film, paper = _install_stock_selectors(app.widgets, app.controller)
    history = EditHistory(widgets=app.widgets, gui=app.controller, viewer=app.viewer)
    actions = ViewerActions(viewer=app.viewer, gui=app.controller)
    compare_button = _install_compare_button(main_window, actions)
    _install_reset_button(app.widgets, app.viewer)
    batch.workspace_tools = (film, paper, history, actions)
    simulation = app.widgets.simulation
    batch.folder_rejected.connect(folders.reveal)

    def leave_compare_silently() -> None:
        was_blocked = compare_button.blockSignals(True)
        compare_button.setChecked(False)
        compare_button.blockSignals(was_blocked)

    app.controller.set_output_shown_listener(leave_compare_silently)
    simulation.save_button.pressed.connect(lambda: compare_button.setChecked(False))
    # Importing happens from the header and strip; this panel keeps only the RAW development settings.
    app.widgets.load_raw.reprocess_button.parentWidget().layout().setRowVisible(0, False)

    def sync_slider_defaults(*_args) -> None:
        refresh_slider_defaults(widgets=app.widgets, film_stock=film.current_value(), print_paper=paper.current_value())

    film.changed.connect(sync_slider_defaults)
    paper.changed.connect(sync_slider_defaults)
    sync_slider_defaults()

    def open_folder_from_dialog() -> None:
        directory = batch.choose_folder()
        if directory:
            folders.reveal(directory)

    header.open_folder_button.clicked.connect(open_folder_from_dialog)
    _install_shortcuts(main_window, {
        'Ctrl+Z': history.undo,
        'Ctrl+Y': history.redo,
        'Ctrl+Shift+Z': history.redo,
        'Ctrl+O': open_folder_from_dialog,
        'Ctrl+E': batch.run_export,
        'Ctrl+S': simulation.save_button.click,
        'Ctrl+Return': simulation.scan_button.click,
        '\\': compare_button.toggle,
        'Z': actions.toggle_zoom,
        '[': lambda: film.step(-1),
        ']': lambda: film.step(1),
    })

    _wrap_with_header(main_window, header)
    _dress_viewer_toolbar(main_window)
    _dress_tabs(main_window)
    _reorder_main_tab(app.widgets)
    _attach_strip(main_window, strip)
    _attach_folder_panel(main_window, folders)
    _remember_section_states(main_window)
    QtCore.QTimer.singleShot(0, folders.restore_last_folder)
    return batch
