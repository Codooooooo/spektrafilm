"""Editing conveniences borrowed from mature photo tools: undo, reset, before/after."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from qtpy import QtCore

from spektrafilm_gui.app import connect_auto_preview_signals
from spektrafilm_gui.controller_layers import OUTPUT_LAYER_NAME
from spektrafilm_gui.napari_layout import reset_viewer_camera, set_status, set_viewer_zoom_percent
from spektrafilm_gui.state import build_default_gui_state, clone_gui_state
from spektrafilm_gui.state_bridge import (
    GUI_STATE_SECTION_NAMES,
    SECTION_STATE_ACCESSORS,
    apply_gui_state,
    collect_gui_state,
)
from spektrafilm_gui.widget_editors import SliderSpinEditor

MAX_HISTORY = 100
SNAPSHOT_DELAY_MS = 350


class EditHistory(QtCore.QObject):
    """Undo stack of GUI states, one step per pause in editing."""

    def __init__(self, *, widgets: Any, gui: Any, viewer: Any) -> None:
        super().__init__()
        self._widgets = widgets
        self._gui = gui
        self._viewer = viewer
        self._undo: list[Any] = [collect_gui_state(widgets=widgets)]
        self._redo: list[Any] = []
        self._restoring = False
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SNAPSHOT_DELAY_MS)
        self._timer.timeout.connect(self._snapshot)
        connect_auto_preview_signals(self, widgets)

    def request_auto_preview(self, *_args) -> None:
        if not self._restoring:
            self._timer.start()

    def undo(self) -> None:
        self._flush()
        if len(self._undo) <= 1:
            set_status(self._viewer, '没有可撤销的操作')
            return
        self._redo.append(self._undo.pop())
        self._restore(self._undo[-1])
        set_status(self._viewer, '已撤销')

    def redo(self) -> None:
        self._flush()
        if not self._redo:
            set_status(self._viewer, '没有可重做的操作')
            return
        state = self._redo.pop()
        self._undo.append(state)
        self._restore(state)
        set_status(self._viewer, '已重做')

    def _flush(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._snapshot()

    def _snapshot(self) -> None:
        state = collect_gui_state(widgets=self._widgets)
        if repr(state) == repr(self._undo[-1]):
            return
        self._undo.append(state)
        del self._undo[:-MAX_HISTORY]
        self._redo.clear()

    def _restore(self, state: Any) -> None:
        self._restoring = True
        try:
            apply_gui_state(state, widgets=self._widgets)
        finally:
            self._restoring = False
        self._gui._sync_canvas_background()  # pylint: disable=protected-access


@lru_cache(maxsize=64)
def _default_state(film_stock: str, print_paper: str) -> Any:
    return build_default_gui_state(film_stock=film_stock, print_paper=print_paper)


def refresh_slider_defaults(*, widgets: Any, film_stock: str, print_paper: str) -> None:
    """Point every slider's double-click target at this film and paper's default."""
    defaults = _default_state(film_stock, print_paper)
    for name in GUI_STATE_SECTION_NAMES:
        section = getattr(widgets, name)
        section_state = SECTION_STATE_ACCESSORS[name].get(defaults)
        specs = getattr(section, '_specs', None)
        for leaf, editor in getattr(section, '_editors', {}).items():
            if not isinstance(editor, SliderSpinEditor):
                continue
            path = specs[leaf].path if specs else leaf
            value: Any = section_state
            for part in path.split('.'):
                value = getattr(value, part)
            editor.set_default(float(value))


def reset_look_to_defaults(*, widgets: Any, viewer: Any) -> None:
    """Restore the current film and paper's defaults, keeping the workflow settings."""
    current = collect_gui_state(widgets=widgets)
    fresh = clone_gui_state(_default_state(current.selection.film_stock, current.selection.print_paper))
    fresh.gui_only = current.gui_only
    fresh.input_image = current.input_image
    fresh.simulation.workflow = current.simulation.workflow
    fresh.simulation.io.output_color_space = current.simulation.io.output_color_space
    apply_gui_state(fresh, widgets=widgets)
    set_status(viewer, '已恢复当前胶片和相纸的默认参数，可按 Ctrl+Z 撤销')


class ViewerActions:
    """Before/after comparison and the fit / 100% zoom toggle."""

    def __init__(self, *, viewer: Any, gui: Any) -> None:
        self._viewer = viewer
        self._gui = gui
        self._zoomed = False

    def is_comparing(self) -> bool:
        layers = self._gui._layers  # pylint: disable=protected-access
        preview = layers.preview_input_layer()
        return preview is not None and bool(preview.visible)

    def set_comparing(self, comparing: bool) -> None:
        layers = self._gui._layers  # pylint: disable=protected-access
        output = layers.image_layer(OUTPUT_LAYER_NAME)
        preview = layers.preview_input_layer()
        if output is None or preview is None:
            return
        layers.hide_layer(OUTPUT_LAYER_NAME) if comparing else setattr(output, 'visible', True)
        preview.visible = comparing
        set_status(self._viewer, '正在显示原图' if comparing else '正在显示胶片效果', timeout_ms=1500)

    def toggle_compare(self) -> None:
        self.set_comparing(not self.is_comparing())

    def toggle_zoom(self) -> None:
        self._zoomed = not self._zoomed
        if self._zoomed:
            set_viewer_zoom_percent(self._viewer, 100.0)
        else:
            reset_viewer_camera(self._viewer)
