"""Visual film and paper library that replaces the plain drop-down lists.

The hidden combo boxes stay as the source of truth, so saved settings, profile
defaults and auto preview keep working unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import threading
from typing import Any

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from spektrafilm.profiles.io import load_profile
from spektrafilm_gui import controller as gui_controller
from spektrafilm_gui.batch_panel import _pixmap_from_rgb
from spektrafilm_gui.params_mapper import build_params_from_state
from spektrafilm_gui.state_bridge import collect_gui_state
from spektrafilm_gui.theme_palette import SURFACE_INPUT, TEXT_DIM, TEXT_MAIN
from spektrafilm_gui.ui_icons import ui_icon

Qt = QtCore.Qt
Signal = QtCore.Signal
QObject = getattr(QtCore, 'QObject')
QRunnable = getattr(QtCore, 'QRunnable')
VALUE_ROLE = int(Qt.UserRole)
BROWSER_SIZE = QtCore.QSize(610, 660)
TILE_ICON_SIZE = QtCore.QSize(168, 112)
TILE_CELL_SIZE = QtCore.QSize(186, 150)
SAMPLE_LONG_EDGE = 224
MAX_CACHED_SAMPLES = 400
ALL_CHIP = '全部'
FAVORITES_CHIP = '★ 收藏'


@dataclass(frozen=True, slots=True)
class StockInfo:
    value: str
    name: str
    category: str
    target_print: str | None
    is_positive: bool


@lru_cache(maxsize=None)
def stock_info(value: str) -> StockInfo:
    profile = load_profile(value)
    if profile.info.stage == 'printing':
        category = '电影拷贝' if profile.is_cine else '相纸'
    elif profile.is_positive:
        category = '反转片'
    else:
        category = '电影胶片' if profile.is_cine else '彩色负片'
    return StockInfo(value, profile.info.name, category, profile.info.target_print, bool(profile.is_positive))


def _load_favorites(kind: str) -> set[str]:
    stored = QtCore.QSettings('spektrafilm', 'spektrafilm').value(f'favorites/{kind}', [])
    if isinstance(stored, str):
        stored = [stored]
    return set(stored or [])


def _save_favorites(kind: str, favorites: set[str]) -> None:
    QtCore.QSettings('spektrafilm', 'spektrafilm').setValue(f'favorites/{kind}', sorted(favorites))


def _icon_button(icon_name: str, tooltip: str) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton()
    button.setIcon(ui_icon(icon_name, TEXT_MAIN))
    button.setIconSize(QtCore.QSize(14, 14))
    button.setToolTip(tooltip)
    button.setProperty('role', 'stockStep')
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedSize(28, 28)
    return button


class _SampleSignals(QObject):
    ready = Signal(str, object, object)


class _SampleWorker(QRunnable):
    """Renders one small sample of the current photo per film or paper."""

    def __init__(self, kind: str, values: list[str], image: np.ndarray, state: Any, cache_key: tuple):
        super().__init__()
        self._kind = kind
        self._values = values
        self._image = image
        self._state = state
        self._cache_key = cache_key
        self._cancel = threading.Event()
        self.signals = _SampleSignals()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        image = np.double(gui_controller.resize_for_preview(self._image, SAMPLE_LONG_EDGE))
        for value in self._values:
            if self._cancel.is_set():
                return
            try:
                self.signals.ready.emit(value, self._cache_key, self._render(value, image))
            except Exception:  # pylint: disable=broad-exception-caught - a missing sample must not stop the rest
                continue

    def _render(self, value: str, image: np.ndarray) -> np.ndarray:
        state = deepcopy(self._state)
        if self._kind == 'film':
            state.selection.film_stock = value
        else:
            state.selection.print_paper = value
        params = build_params_from_state(state)
        params.settings.preview_mode = True
        params.io.scan_film = bool(params.film.is_positive)
        with gui_controller.runtime.SIMULATION_LOCK:
            simulator = gui_controller.runtime_simulator(gui_controller.digest_params(params, apply_stocks_specifics=True))
            scan = simulator.process(image)
        display, _status = gui_controller.GuiController._prepare_output_display_image(  # pylint: disable=protected-access
            scan,
            output_color_space=state.simulation.io.output_color_space,
            use_display_transform=state.gui_only.display.use_display_transform,
        )
        return np.asarray(display, dtype=np.uint8)


class StockBrowser(QtWidgets.QFrame):
    """Popup library: click applies at once and stays open so looks can be compared."""

    def __init__(self, selector: 'StockSelector', parent: QtWidgets.QWidget) -> None:
        super().__init__(parent, Qt.Popup)
        self._selector = selector
        self._items: dict[str, QtWidgets.QListWidgetItem] = {}
        self._active_chip = ALL_CHIP
        self.setObjectName('stockBrowser')
        self.setFixedSize(BROWSER_SIZE)

        title = QtWidgets.QLabel('选择胶片' if selector.kind == 'film' else '选择相纸')
        title.setObjectName('dialogHeading')
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('搜索名称，例如 portra、vision、富士')
        self.search.setClearButtonEnabled(True)
        self.search.addAction(ui_icon('search', TEXT_DIM), QtWidgets.QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._apply_filter)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(title)
        header.addWidget(self.search, 1)

        self.chips = QtWidgets.QHBoxLayout()
        self.chips.setSpacing(6)
        categories = list(dict.fromkeys(stock_info(value).category for value in selector.values))
        self._chip_buttons: dict[str, QtWidgets.QPushButton] = {}
        for label in (ALL_CHIP, FAVORITES_CHIP, *categories):
            chip = QtWidgets.QPushButton(label)
            chip.setCheckable(True)
            chip.setProperty('role', 'chip')
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _checked=False, name=label: self._select_chip(name))
            self.chips.addWidget(chip)
            self._chip_buttons[label] = chip
        self.chips.addStretch(1)

        self.list = QtWidgets.QListWidget()
        self.list.setObjectName('filmStrip')
        self.list.setViewMode(QtWidgets.QListView.IconMode)
        self.list.setMovement(QtWidgets.QListView.Static)
        self.list.setResizeMode(QtWidgets.QListView.Adjust)
        self.list.setUniformItemSizes(True)
        self.list.setIconSize(TILE_ICON_SIZE)
        self.list.setGridSize(TILE_CELL_SIZE)
        self.list.setWordWrap(True)
        self.list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.itemDoubleClicked.connect(lambda _item: self.close())
        self.list.customContextMenuRequested.connect(self._show_context_menu)

        self.hint = QtWidgets.QLabel('点击即可应用，右键加入收藏，点击窗口外或按 Esc 关闭')
        self.hint.setObjectName('dialogNote')

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 8, 12)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addLayout(self.chips)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.hint)
        self._populate()
        self._select_chip(ALL_CHIP)

    def open_at(self, anchor: QtWidgets.QWidget) -> None:
        self._populate()
        self._apply_filter()
        top_left = anchor.mapToGlobal(QtCore.QPoint(-BROWSER_SIZE.width() - 14, 0))
        screen = anchor.screen().availableGeometry()
        x = max(screen.left() + 8, top_left.x())
        y = max(screen.top() + 8, min(top_left.y(), screen.bottom() - BROWSER_SIZE.height() - 8))
        self.move(x, y)
        self.show()
        self.search.setFocus()

    def set_sample(self, value: str, image: np.ndarray) -> None:
        item = self._items.get(value)
        if item is not None:
            item.setIcon(QtGui.QIcon(_pixmap_from_rgb(image)))

    def refresh_current(self) -> None:
        current = self._items.get(self._selector.current_value())
        if current is not None:
            self.list.setCurrentItem(current)

    def _populate(self) -> None:
        favorites = self._selector.favorites
        recommended = self._selector.recommended_value
        order = sorted(
            self._selector.values,
            key=lambda value: (value not in favorites, value != recommended, stock_info(value).name),
        )
        placeholder = QtGui.QPixmap(TILE_ICON_SIZE)
        placeholder.fill(QtGui.QColor(SURFACE_INPUT))
        self.list.clear()
        self._items.clear()
        for value in order:
            info = stock_info(value)
            star = '★ ' if value in favorites else ''
            suffix = '\n推荐搭配' if value == recommended else ''
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(placeholder), f'{star}{info.name}{suffix}')
            item.setData(VALUE_ROLE, value)
            item.setToolTip(f'{info.name}\n{info.category}')
            self.list.addItem(item)
            self._items[value] = item
        self._selector.restore_samples(self)
        self.refresh_current()

    def _select_chip(self, name: str) -> None:
        self._active_chip = name
        for label, chip in self._chip_buttons.items():
            chip.setChecked(label == name)
        self._apply_filter()

    def _apply_filter(self, *_args) -> None:
        needle = self.search.text().strip().lower()
        favorites = self._selector.favorites
        for value, item in self._items.items():
            info = stock_info(value)
            matches_text = not needle or needle in f'{info.name} {value} {info.category}'.lower() or (needle == '富士' and 'fuji' in value)
            matches_chip = (
                self._active_chip == ALL_CHIP
                or (self._active_chip == FAVORITES_CHIP and value in favorites)
                or self._active_chip == info.category
            )
            item.setHidden(not (matches_text and matches_chip))

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        self._selector.select(item.data(VALUE_ROLE))

    def _show_context_menu(self, position: QtCore.QPoint) -> None:
        item = self.list.itemAt(position)
        if item is None:
            return
        value = item.data(VALUE_ROLE)
        favorite = value in self._selector.favorites
        menu = QtWidgets.QMenu(self)
        toggle = menu.addAction('取消收藏' if favorite else '加入收藏')
        if menu.exec(self.list.viewport().mapToGlobal(position)) == toggle:
            self._selector.toggle_favorite(value)
            self._populate()
            self._apply_filter()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.close()
            return
        super().keyPressEvent(event)


class StockCard(QtWidgets.QFrame):
    open_requested = Signal()
    step_requested = Signal(int)

    def __init__(self, heading: str) -> None:
        super().__init__()
        self.setObjectName('stockCard')
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('点击打开胶片库，查看每种效果的小样')

        kicker = QtWidgets.QLabel(heading)
        kicker.setObjectName('stockKicker')
        self.name = QtWidgets.QLabel('')
        self.name.setObjectName('stockName')
        self.detail = QtWidgets.QLabel('')
        self.detail.setObjectName('stockDetail')
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(kicker)
        text.addWidget(self.name)
        text.addWidget(self.detail)

        previous_button = _icon_button('chevron-left', '上一个（快捷键 [）')
        next_button = _icon_button('chevron-right', '下一个（快捷键 ]）')
        previous_button.clicked.connect(lambda: self.step_requested.emit(-1))
        next_button.clicked.connect(lambda: self.step_requested.emit(1))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(4)
        layout.addLayout(text, 1)
        layout.addWidget(previous_button)
        layout.addWidget(next_button)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_requested.emit()
        super().mouseReleaseEvent(event)


class StockSelector(QtCore.QObject):
    changed = Signal(str)

    def __init__(self, *, kind: str, heading: str, combo: Any, widgets: Any, gui: Any) -> None:
        super().__init__()
        self.kind = kind
        self.values = [combo.itemText(index) for index in range(combo.count())]
        self.favorites = _load_favorites(kind)
        self.recommended_value: str | None = None
        self.card = StockCard(heading)
        self._combo = combo
        self._widgets = widgets
        self._gui = gui
        self._note = ''
        self._browser: StockBrowser | None = None
        self._samples: dict[tuple[tuple, str], np.ndarray] = {}
        self._worker: _SampleWorker | None = None
        self._active_key: tuple | None = None
        self._pool = QtCore.QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.card.open_requested.connect(self.open_browser)
        self.card.step_requested.connect(self.step)
        combo.currentTextChanged.connect(self._on_combo_changed)
        self._refresh_card()

    def current_value(self) -> str:
        return self._combo.value

    def select(self, value: str) -> None:
        if value == self._combo.value or value not in self.values:
            return
        self._combo.value = value
        self._combo.textActivated.emit(value)

    def step(self, offset: int) -> None:
        index = self.values.index(self._combo.value)
        self.select(self.values[(index + offset) % len(self.values)])

    def toggle_favorite(self, value: str) -> None:
        self.favorites.symmetric_difference_update({value})
        _save_favorites(self.kind, self.favorites)

    def set_context(self, *, note: str = '', recommended: str | None = None) -> None:
        self._note = note
        self.recommended_value = recommended
        self._refresh_card()

    def open_browser(self) -> None:
        if self._browser is None:
            self._browser = StockBrowser(self, self.card.window())
            self._browser.destroyed.connect(self._clear_browser)
        self._browser.open_at(self.card)
        self._render_samples()

    def restore_samples(self, browser: StockBrowser) -> None:
        for (key, value), image in self._samples.items():
            if key == self._active_key:
                browser.set_sample(value, image)

    def _clear_browser(self) -> None:
        self._browser = None

    def _sample_key(self, state: Any, preview: np.ndarray) -> tuple:
        other = state.selection.print_paper if self.kind == 'film' else state.selection.film_stock
        return (
            self._gui._current_input_path,  # pylint: disable=protected-access
            preview.shape,
            other,
            state.camera.auto_exposure,
            state.camera.exposure_compensation_ev,
            state.simulation.enlarger.print_exposure,
            state.simulation.io.output_color_space,
        )

    def _render_samples(self) -> None:
        preview = self._gui._current_preview_image  # pylint: disable=protected-access
        if preview is None:
            return
        state = collect_gui_state(widgets=self._widgets)
        key = self._sample_key(state, preview)
        if self._worker is not None:
            self._worker.cancel()
        self._active_key = key
        if self._browser is not None:
            self.restore_samples(self._browser)
        missing = [value for value in self.values if (key, value) not in self._samples]
        if not missing:
            return
        self._worker = _SampleWorker(self.kind, missing, np.array(preview, copy=True), state, key)
        self._worker.setAutoDelete(False)
        self._worker.signals.ready.connect(self._on_sample_ready)
        self._pool.start(self._worker)

    def _on_sample_ready(self, value: str, key: tuple, image: np.ndarray) -> None:
        if len(self._samples) >= MAX_CACHED_SAMPLES:
            self._samples.clear()
        self._samples[(key, value)] = image
        if key == self._active_key and self._browser is not None:
            self._browser.set_sample(value, image)

    def _on_combo_changed(self, _value: str) -> None:
        self._refresh_card()
        if self._browser is not None:
            self._browser.refresh_current()
        self.changed.emit(self._combo.value)

    def _refresh_card(self) -> None:
        info = stock_info(self._combo.value)
        self.card.name.setText(info.name)
        parts = [self._note or info.category]
        if self._combo.value == self.recommended_value and not self._note:
            parts.append('推荐搭配')
        self.card.detail.setText(' · '.join(parts))
