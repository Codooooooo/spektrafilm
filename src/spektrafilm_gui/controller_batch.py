"""Connects the folder browser and film strip to the viewer and the batch workers."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import time
from typing import Any

import numpy as np
from qtpy import QtCore, QtWidgets

from spektrafilm_gui import controller_runtime as runtime
from spektrafilm_gui.app import connect_auto_preview_signals
from spektrafilm_gui.batch import (
    FORMAT_GROUPS,
    BatchItem,
    BatchJob,
    BatchSummary,
    BatchWorker,
    ExportOptions,
    LoadedPhoto,
    LoadWorker,
    PrerenderedPhoto,
    PrerenderTarget,
    PrerenderWorker,
    ThumbnailWorker,
    format_group,
    is_raw_file,
    is_supported_file,
    photos_in_folder,
    preview_source_key,
)
from spektrafilm_gui.batch_panel import BatchExportDialog, BatchStrip, PHOTO_FILE_FILTER
from spektrafilm_gui.i18n_zh import LocalizedMessageBox
from spektrafilm_gui.napari_layout import dialog_parent, set_status
from spektrafilm_gui.params_mapper import build_params_from_state
from spektrafilm_gui.persistence import load_dialog_dir, save_dialog_dir
from spektrafilm_gui.state_bridge import collect_gui_state

QThreadPool = getattr(QtCore, 'QThreadPool')
MAX_LISTED_FAILURES = 5
LOAD_DELAY_MS = 120
REPEAT_SELECT_WINDOW_S = 0.25
THUMBNAIL_THREADS = 2
PRERENDER_DELAY_MS = 300
PREVIEW_CACHE_SIZE = 48
RESULT_CACHE_SIZE = 32
FORMAT_FILTER_KEY = 'batch/format_filter'


class BatchController(QtCore.QObject):
    current_changed = QtCore.Signal(str, int, int)
    folder_rejected = QtCore.Signal(str)

    def __init__(self, *, viewer: Any, widgets: Any, gui_controller: Any, strip: BatchStrip) -> None:
        super().__init__()
        self._viewer = viewer
        self._widgets = widgets
        self._gui = gui_controller
        self._strip = strip
        self._items: list[BatchItem] = []
        self._index_by_path: dict[str, int] = {}
        self._rotations: dict[str, int] = {}
        self._current: int | None = None
        self._folder: str | None = None
        self._active_worker: BatchWorker | None = None
        self._thumbnail_workers: list[ThumbnailWorker] = []
        self._load_workers: list[LoadWorker] = []
        self._load_workers_keepalive: list[PrerenderWorker] = []
        self._load_token = 0
        self._last_select_time = 0.0
        self._format_filter = str(QtCore.QSettings('spektrafilm', 'spektrafilm').value(FORMAT_FILTER_KEY, ''))
        self._preview_cache: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._result_cache: OrderedDict[tuple, runtime.CachedResult] = OrderedDict()
        self._prerender_worker: PrerenderWorker | None = None
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(1)
        self._thumbnail_pool = QThreadPool()
        self._thumbnail_pool.setMaxThreadCount(THUMBNAIL_THREADS)
        self._load_pool = QThreadPool()
        self._load_pool.setMaxThreadCount(1)
        # Debounced so holding an arrow key skips photos instead of decoding each one.
        self._load_timer = QtCore.QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(LOAD_DELAY_MS)
        self._load_timer.timeout.connect(self._load_current)
        self._prerender_pool = QThreadPool()
        self._prerender_pool.setMaxThreadCount(1)
        self._prerender_timer = QtCore.QTimer(self)
        self._prerender_timer.setSingleShot(True)
        self._prerender_timer.setInterval(PRERENDER_DELAY_MS)
        self._prerender_timer.timeout.connect(self._start_prerender)

        strip.add_requested.connect(self.choose_files)
        strip.files_dropped.connect(self.add_files)
        strip.item_selected.connect(self.select)
        strip.remove_requested.connect(self.remove)
        strip.clear_requested.connect(self.clear)
        strip.preview_requested.connect(self.run_preview)
        strip.export_requested.connect(self.run_export)
        strip.cancel_requested.connect(self.cancel)
        strip.format_filter_changed.connect(self.set_format_filter)
        gui_controller.set_rotation_listener(self._on_rotated)
        gui_controller.set_full_image_loader(self._load_full_image)
        gui_controller.set_reload_listener(self._reload_current)
        gui_controller.set_result_listener(self._on_gui_result)
        connect_auto_preview_signals(self, widgets)

    def choose_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            dialog_parent(self._viewer), '添加照片', load_dialog_dir('batch_input'), PHOTO_FILE_FILTER,
        )
        if paths:
            save_dialog_dir('batch_input', str(Path(paths[0]).parent))
            self.add_files(paths)

    def choose_folder(self) -> str:
        return QtWidgets.QFileDialog.getExistingDirectory(
            dialog_parent(self._viewer), '打开文件夹', load_dialog_dir('browse_folder'),
        )

    def open_folder(self, directory: str) -> None:
        if directory == self._folder:
            return
        if self.is_running():
            set_status(self._viewer, '批量任务进行中，完成或取消后才能切换文件夹')
            if self._folder:
                self.folder_rejected.emit(self._folder)
            return
        try:
            photos = photos_in_folder(directory)
        except OSError as exc:
            set_status(self._viewer, f'无法读取这个文件夹：{exc}')
            return
        self._folder = directory
        self._reset_list()
        if not photos:
            self._refresh_filter()
            self._announce_current()
            set_status(self._viewer, f'{Path(directory).name or directory} 里没有支持的照片')
            return
        self._append(photos)
        self._refresh_filter()
        set_status(self._viewer, f'{Path(directory).name or directory}：{len(photos)} 张照片')
        self.select(self._visible_indices()[0])

    def add_files(self, paths: list[str]) -> None:
        expanded: list[str] = []
        for path in paths:
            if Path(path).is_dir():
                try:
                    expanded.extend(photos_in_folder(path))
                except OSError:
                    continue
            else:
                expanded.append(path)
        existing = {item.path for item in self._items}
        accepted = [path for path in dict.fromkeys(expanded) if is_supported_file(path) and path not in existing]
        skipped = len(expanded) - len(accepted)
        if not accepted:
            set_status(self._viewer, '没有可添加的新照片')
            return

        first_new = len(self._items)
        self._append(accepted)
        self._refresh_filter()
        message = f'已添加 {len(accepted)} 张照片'
        set_status(self._viewer, f'{message}，跳过 {skipped} 个重复或不支持的文件' if skipped else message)
        if self._current is None:
            visible = [index for index in self._visible_indices() if index >= first_new]
            if visible:
                self.select(visible[0])
        else:
            self._announce_current()

    def select(self, index: int) -> None:
        if not 0 <= index < len(self._items) or index == self._current:
            return
        self._current = index
        self._strip.set_current(index)
        self._announce_current()
        self._load_token += 1
        self._cancel_prerender()
        # A lone click opens at once; only rapid stepping waits for the user to settle.
        now = time.monotonic()
        rapid = now - self._last_select_time < REPEAT_SELECT_WINDOW_S
        self._last_select_time = now
        if rapid:
            self._load_timer.start()
        else:
            self._load_timer.stop()
            self._load_current()

    def set_format_filter(self, group: str) -> None:
        self._format_filter = group
        QtCore.QSettings('spektrafilm', 'spektrafilm').setValue(FORMAT_FILTER_KEY, group)
        self._refresh_filter()
        visible = self._visible_indices()
        if visible and self._current not in visible:
            self.select(visible[0])
        else:
            self._announce_current()
        self._schedule_prerender()

    def request_auto_preview(self, *_args) -> None:
        """Any parameter edit makes neighbouring prerenders stale."""
        self._cancel_prerender()
        self._schedule_prerender()

    def remove(self, index: int) -> None:
        if self.is_running() or not 0 <= index < len(self._items):
            return
        del self._items[index]
        self._index_by_path = {item.path: position for position, item in enumerate(self._items)}
        self._strip.take_item(index)
        if self._current is not None:
            if index < self._current:
                self._current -= 1
            elif index == self._current:
                self._current = None
        self._refresh_filter()
        self._announce_current()

    def clear(self) -> None:
        if self.is_running():
            return
        self._folder = None
        self._reset_list()
        self._refresh_filter()
        self._announce_current()

    def is_running(self) -> bool:
        return self._active_worker is not None

    def run_preview(self) -> None:
        if not self._require_items('批量预览'):
            return
        self._start_job('preview')

    def run_export(self) -> None:
        if not self._require_items('批量输出'):
            return
        dialog = BatchExportDialog(dialog_parent(self._viewer), len(self._visible_indices()))
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        directory = dialog.directory_value()
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as exc:
            LocalizedMessageBox.critical(dialog_parent(self._viewer), '批量输出', f'无法使用这个输出文件夹。\n\n{exc}')
            return
        dialog.remember_directory()
        self._start_job('export', ExportOptions(directory, dialog.extension_value(), dialog.suffix_value()))

    def cancel(self) -> None:
        if self._active_worker is not None:
            self._active_worker.cancel()
            self._strip.progress_label.setText('正在停止……')

    def _visible_indices(self) -> list[int]:
        return [
            index for index, item in enumerate(self._items)
            if not self._format_filter or format_group(item.path) == self._format_filter
        ]

    def _refresh_filter(self) -> None:
        counts = {group: 0 for group in FORMAT_GROUPS}
        for item in self._items:
            counts[format_group(item.path)] += 1
        counts = {group: count for group, count in counts.items() if count}
        if self._format_filter not in counts:
            self._format_filter = ''
        self._strip.set_format_counts(counts, self._format_filter)
        visible = set(self._visible_indices())
        for index in range(len(self._items)):
            self._strip.set_row_hidden(index, index not in visible)
        self._strip.set_visible_count(len(visible), len(self._items))

    def _reset_list(self) -> None:
        self._cancel_prerender()
        for worker in self._thumbnail_workers:
            worker.cancel()
        self._thumbnail_workers.clear()
        self._load_token += 1
        self._load_timer.stop()
        self._items.clear()
        self._index_by_path.clear()
        self._current = None
        self._strip.clear_items()

    def _append(self, paths: list[str]) -> None:
        for path in paths:
            self._index_by_path[path] = len(self._items)
            self._items.append(BatchItem(path=path, quarter_turns=self._rotations.get(path, 0)))
        self._strip.add_items(paths)
        worker = ThumbnailWorker(paths, collect_gui_state(widgets=self._widgets))
        worker.setAutoDelete(False)
        worker.signals.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumbnail_workers.append(worker)
        self._thumbnail_pool.start(worker)

    def _reload_current(self) -> None:
        self._load_token += 1
        self._load_current(use_cache=False)

    def _load_current(self, *, use_cache: bool = True) -> None:
        if self._current is None:
            return
        path = self._items[self._current].path
        state = collect_gui_state(widgets=self._widgets)
        if use_cache:
            preview = self._cache_get(self._preview_cache, (path, preview_source_key(state)))
            if preview is not None:
                turns = self._rotations.get(path, 0)
                result = self._cache_get(self._result_cache, (path, turns, runtime.look_key(state)))
                self._show_photo(path, preview, preview, is_proxy=True, cached_result=result)
                return
        set_status(self._viewer, f'正在打开 {Path(path).name}……', timeout_ms=0)
        worker = LoadWorker(self._load_token, path, state, self._is_current_load)
        worker.setAutoDelete(False)
        worker.signals.loaded.connect(self._on_loaded)
        worker.signals.load_failed.connect(self._on_load_failed)
        self._load_workers.append(worker)
        self._load_pool.start(worker)

    def _is_current_load(self, token: int) -> bool:
        return token == self._load_token

    def _load_full_image(self, path: str) -> None:
        worker = LoadWorker(0, path, collect_gui_state(widgets=self._widgets), lambda _token: True, full=True)
        worker.setAutoDelete(False)
        worker.signals.loaded.connect(self._on_full_loaded)
        worker.signals.load_failed.connect(self._on_full_failed)
        self._load_workers.append(worker)
        self._load_pool.start(worker)

    def _on_full_loaded(self, _token: int, path: str, photo: LoadedPhoto) -> None:
        self._drop_finished_load_worker()
        self._gui.on_full_image_loaded(path, photo.image)

    def _on_full_failed(self, _token: int, path: str, message: str) -> None:
        self._drop_finished_load_worker()
        self._gui.on_full_image_failed(path, message)

    def _on_loaded(self, token: int, path: str, photo: LoadedPhoto) -> None:
        self._drop_finished_load_worker()
        if not self._is_current_load(token):
            return
        preview = np.asarray(photo.preview, dtype=np.float32)
        state = collect_gui_state(widgets=self._widgets)
        self._cache_put(self._preview_cache, (path, preview_source_key(state)), preview, PREVIEW_CACHE_SIZE)
        self._show_photo(path, photo.image, preview, is_proxy=photo.is_proxy)

    def _show_photo(self, path: str, image: Any, preview: Any, *, is_proxy: bool, cached_result: Any = None) -> None:
        self._gui.show_loaded_image(
            path, image,
            preview_image=preview,
            is_proxy=is_proxy,
            keep_output=True,
            quarter_turns=self._rotations.get(path, 0),
            cached_result=cached_result,
        )
        if is_raw_file(path):
            self._widgets.load_raw.set_path(path)
        set_status(self._viewer, Path(path).name)
        # Leave focus on the strip so arrow keys keep browsing, unless the user is typing or in the tree.
        focused = QtWidgets.QApplication.focusWidget()
        if not isinstance(focused, (QtWidgets.QAbstractSpinBox, QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QTreeView)):
            self._strip.list.setFocus()

    def _on_load_failed(self, token: int, path: str, message: str) -> None:
        self._drop_finished_load_worker()
        if self._is_current_load(token):
            set_status(self._viewer, f'无法打开 {Path(path).name}：{message}', timeout_ms=15000)
        index = self._index_by_path.get(path)
        if index is not None:
            self._strip.mark_failed(index)

    def _drop_finished_load_worker(self) -> None:
        if self._load_workers:
            self._load_workers.pop(0)

    def _require_items(self, title: str) -> bool:
        if self.is_running():
            return False
        if self._visible_indices():
            return True
        LocalizedMessageBox.warning(dialog_parent(self._viewer), title, '请先添加照片。')
        return False

    def _start_job(self, mode: str, options: ExportOptions | None = None) -> None:
        state = collect_gui_state(widgets=self._widgets)
        self._cancel_prerender()
        items = [(index, self._items[index]) for index in self._visible_indices()]
        job = BatchJob(mode=mode, items=items, state=state, params=build_params_from_state(state), options=options)
        worker = BatchWorker(job)
        worker.signals.item_rendered.connect(self._on_item_rendered)
        worker.signals.item_failed.connect(self._on_item_failed)
        worker.signals.progress.connect(self._strip.set_progress)
        worker.signals.finished.connect(self._on_finished)
        self._active_worker = worker
        self._strip.set_running(True)
        self._gui.set_batch_running(True)
        set_status(self._viewer, '正在批量预览……' if mode == 'preview' else '正在批量输出……', timeout_ms=0)
        self._pool.start(worker)

    def _on_thumbnail_ready(self, path: str, image: Any) -> None:
        index = self._index_by_path.get(path)
        if index is not None and not self._items[index].is_rendered:
            self._strip.set_thumbnail(index, image)

    def _on_item_rendered(self, index: int, image: Any) -> None:
        if 0 <= index < len(self._items):
            self._items[index].display = image
            self._items[index].is_rendered = True
            self._strip.set_thumbnail(index, image)

    def _on_item_failed(self, index: int, _message: str) -> None:
        self._strip.mark_failed(index)

    def _on_gui_result(self, path: str, look_key: int, result: Any) -> None:
        cached = runtime.CachedResult(
            np.asarray(result.display_image, dtype=np.uint8),
            np.asarray(result.float_image, dtype=np.float32),
            result.output_color_space,
            result.use_display_transform,
        )
        self._cache_put(self._result_cache, (path, self._rotations.get(path, 0), look_key), cached, RESULT_CACHE_SIZE)
        self._schedule_prerender()

    def _on_prerendered(self, photo: PrerenderedPhoto) -> None:
        self._cache_put(self._preview_cache, (photo.path, photo.source_key), photo.preview, PREVIEW_CACHE_SIZE)
        self._cache_put(self._result_cache, (photo.path, photo.quarter_turns, photo.look_key), photo.result, RESULT_CACHE_SIZE)

    def _schedule_prerender(self) -> None:
        self._prerender_timer.start()

    def _cancel_prerender(self) -> None:
        self._prerender_timer.stop()
        if self._prerender_worker is not None:
            self._prerender_worker.cancel()
            self._prerender_worker = None

    def _neighbour_paths(self) -> list[str]:
        visible = self._visible_indices()
        if self._current not in visible:
            return []
        position = visible.index(self._current)
        offsets = (1, -1, 2)
        targets = [visible[position + offset] for offset in offsets if 0 <= position + offset < len(visible)]
        return [self._items[index].path for index in targets]

    def _start_prerender(self) -> None:
        if self._gui.is_simulating() or self.is_running():
            self._schedule_prerender()
            return
        state = collect_gui_state(widgets=self._widgets)
        if not state.simulation.workflow.auto_preview:
            return
        look_key = runtime.look_key(state)
        source_key = preview_source_key(state)
        targets = [
            PrerenderTarget(path, self._rotations.get(path, 0), self._preview_cache.get((path, source_key)))
            for path in self._neighbour_paths()
            if (path, self._rotations.get(path, 0), look_key) not in self._result_cache
        ]
        if not targets:
            return
        worker = PrerenderWorker(targets, state, build_params_from_state(state))
        worker.setAutoDelete(False)
        worker.signals.prerendered.connect(self._on_prerendered)
        self._prerender_worker = worker
        self._load_workers_keepalive.append(worker)
        del self._load_workers_keepalive[:-8]
        self._prerender_pool.start(worker)

    @staticmethod
    def _cache_get(cache: OrderedDict, key: tuple) -> Any:
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value

    @staticmethod
    def _cache_put(cache: OrderedDict, key: tuple, value: Any, limit: int) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)

    def _on_finished(self, summary: BatchSummary) -> None:
        self._active_worker = None
        self._strip.set_running(False)
        self._gui.set_batch_running(False)
        action = '批量预览' if summary.mode == 'preview' else '批量输出'
        if summary.cancelled:
            message = f'{action}已取消，完成 {summary.completed} 张'
        elif summary.mode == 'export':
            message = f'批量输出完成：{summary.completed} 张，保存在 {summary.directory}'
        else:
            message = f'批量预览完成：{summary.completed} 张'
        set_status(self._viewer, message, timeout_ms=15000)
        if summary.failures:
            listed = '\n'.join(f'{Path(path).name or "参数"}：{error}' for path, error in summary.failures[:MAX_LISTED_FAILURES])
            more = len(summary.failures) - MAX_LISTED_FAILURES
            extra = f'\n……还有 {more} 张' if more > 0 else ''
            LocalizedMessageBox.warning(dialog_parent(self._viewer), action, f'{len(summary.failures)} 张处理失败：\n\n{listed}{extra}')

    def _on_rotated(self, quarter_turns: int) -> None:
        if self._current is not None:
            item = self._items[self._current]
            item.quarter_turns = (item.quarter_turns + quarter_turns) % 4
            self._rotations[item.path] = item.quarter_turns
            self._schedule_prerender()

    def _announce_current(self) -> None:
        if self._current is None:
            self.current_changed.emit('', 0, len(self._items))
            return
        visible = self._visible_indices()
        position = visible.index(self._current) + 1 if self._current in visible else 0
        self.current_changed.emit(Path(self._items[self._current].path).name, position, len(visible))
