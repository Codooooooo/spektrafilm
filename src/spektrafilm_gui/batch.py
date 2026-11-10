"""Multi-photo processing: one set of GUI parameters applied to a list of files.

Everything here runs on a worker thread and talks to the GUI through signals.
Stock specifics are not re-applied when digesting because the GUI state already
carries them, along with any edits the user made on top.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
import threading
from typing import Any, Callable

import numpy as np
from qtpy import QtCore

from spektrafilm_gui import controller as gui_controller

QObject = getattr(QtCore, 'QObject')
QRunnable = getattr(QtCore, 'QRunnable')
Signal = getattr(QtCore, 'Signal')

RAW_EXTENSIONS = frozenset({
    '.3fr', '.arw', '.cr2', '.cr3', '.crw', '.dcr', '.dng', '.erf', '.iiq', '.kdc', '.mef', '.mos',
    '.mrw', '.nef', '.nrw', '.orf', '.pef', '.raf', '.raw', '.rw2', '.rwl', '.sr2', '.srf', '.srw', '.x3f',
})
IMAGE_EXTENSIONS = frozenset({'.exr', '.jpeg', '.jpg', '.png', '.tif', '.tiff'})
SUPPORTED_EXTENSIONS = RAW_EXTENSIONS | IMAGE_EXTENSIONS
FORMAT_GROUPS = {
    'RAW': RAW_EXTENSIONS,
    'JPEG': frozenset({'.jpg', '.jpeg'}),
    'TIFF': frozenset({'.tif', '.tiff'}),
    'PNG': frozenset({'.png'}),
    'EXR': frozenset({'.exr'}),
}
JPEG_DRAFT_MARGIN = 2
THUMBNAIL_LONG_EDGE = 480
THUMBNAIL_CACHE_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'spektrafilm' / 'thumbnails'
THUMBNAIL_CACHE_MAX_FILES = 20000


@dataclass(slots=True)
class BatchItem:
    path: str
    quarter_turns: int = 0
    preview_input: np.ndarray | None = None
    preview_key: tuple | None = None
    display: np.ndarray | None = None
    is_rendered: bool = False


@dataclass(frozen=True, slots=True)
class ExportOptions:
    directory: str
    extension: str
    suffix: str


@dataclass(frozen=True, slots=True)
class BatchSummary:
    mode: str
    completed: int
    failures: tuple[tuple[str, str], ...]
    cancelled: bool
    directory: str | None = None


@dataclass(slots=True)
class BatchJob:
    mode: str
    items: list[tuple[int, BatchItem]]
    state: Any
    params: Any
    options: ExportOptions | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


def is_raw_file(path: str) -> bool:
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def is_supported_file(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def format_group(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return next((group for group, extensions in FORMAT_GROUPS.items() if suffix in extensions), '')


def _natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name.lower())]


def photos_in_folder(directory: str) -> list[str]:
    """Supported photos directly inside ``directory``, in natural filename order."""
    entries = (entry for entry in Path(directory).iterdir() if entry.is_file() and is_supported_file(entry.name))
    return [str(entry) for entry in sorted(entries, key=lambda entry: _natural_key(entry.name))]


def load_source_image(path: str, state: Any, *, half_size: bool = False) -> np.ndarray:
    if not is_raw_file(path):
        return gui_controller.load_image_oiio(path)[..., :3]
    raw_settings = state.gui_only.load_raw
    return gui_controller.load_and_process_raw_file(
        path,
        white_balance=raw_settings.white_balance,
        temperature=raw_settings.temperature,
        tint=raw_settings.tint,
        lens_correction=raw_settings.lens_correction,
        output_colorspace=state.input_image.io.input_color_space,
        output_cctf_encoding=state.input_image.io.input_cctf_decoding,
        lens_info_out={},
        half_size=half_size,
    )


def _decode_jpeg_for_preview(path: str, long_edge: int) -> np.ndarray | None:
    """Reduced-size JPEG decode: libjpeg scales in the DCT domain, far faster than a full decode."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as image:
            image.draft('RGB', (long_edge, long_edge))
            if image.mode != 'RGB':
                return None
            return np.asarray(image, dtype=np.float64) / 255.0
    except (OSError, ValueError, UnidentifiedImageError):
        return None


def load_preview_source(path: str, state: Any) -> tuple[np.ndarray, bool]:
    """Decode just enough for a preview; returns the image and whether it is reduced."""
    if is_raw_file(path):
        return load_source_image(path, state, half_size=True), True
    if Path(path).suffix.lower() in FORMAT_GROUPS['JPEG']:
        max_size = state.gui_only.display.settings.preview_max_size
        drafted = _decode_jpeg_for_preview(path, max_size * JPEG_DRAFT_MARGIN)
        if drafted is not None:
            return drafted, True
    return load_source_image(path, state), False


def preview_source_key(state: Any) -> tuple:
    raw_settings = state.gui_only.load_raw
    return (
        raw_settings.white_balance,
        raw_settings.temperature,
        raw_settings.tint,
        raw_settings.lens_correction,
        state.input_image.io.input_color_space,
        state.input_image.io.input_cctf_decoding,
        state.gui_only.display.settings.preview_max_size,
    )


def unique_output_path(directory: str, stem: str, extension: str) -> Path:
    """Return a path in ``directory`` that does not overwrite an existing file."""
    candidate = Path(directory) / f'{stem}{extension}'
    counter = 2
    while candidate.exists():
        candidate = Path(directory) / f'{stem}_{counter}{extension}'
        counter += 1
    return candidate


def encode_for_saving(image: np.ndarray, *, source_color_space: str, saving_color_space: str, saving_cctf_encoding: bool) -> np.ndarray:
    """Match ``GuiController.save_output_layer``: simulation output is CCTF-encoded."""
    if source_color_space == saving_color_space and saving_cctf_encoding:
        return image
    return gui_controller.colour.RGB_to_RGB(
        image,
        source_color_space,
        saving_color_space,
        apply_cctf_decoding=True,
        apply_cctf_encoding=saving_cctf_encoding,
    )


def extract_thumbnail(path: str, state: Any) -> np.ndarray:
    """A display-ready RGB thumbnail, from the disk cache when possible."""
    cache_path = _thumbnail_cache_path(path)
    cached = _read_cached_thumbnail(cache_path)
    if cached is not None:
        return cached
    thumbnail = _decode_thumbnail(path, state)
    _write_cached_thumbnail(cache_path, thumbnail)
    return thumbnail


def _thumbnail_cache_path(path: str) -> Path:
    stat = os.stat(path)
    identity = f'{path}|{stat.st_mtime_ns}|{stat.st_size}|{THUMBNAIL_LONG_EDGE}'
    return THUMBNAIL_CACHE_DIR / f'{hashlib.sha1(identity.encode("utf-8")).hexdigest()}.jpg'


def _read_cached_thumbnail(cache_path: Path) -> np.ndarray | None:
    from PIL import Image

    try:
        with Image.open(cache_path) as image:
            return np.asarray(image.convert('RGB'), dtype=np.uint8)
    except (OSError, ValueError):
        return None


def _write_cached_thumbnail(cache_path: Path, thumbnail: np.ndarray) -> None:
    from PIL import Image

    temporary = cache_path.with_suffix(f'.{threading.get_ident()}.tmp')
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(thumbnail).save(temporary, format='JPEG', quality=88)
        os.replace(temporary, cache_path)
    except OSError:
        temporary.unlink(missing_ok=True)


def prune_thumbnail_cache() -> None:
    """Keep the cache bounded by dropping the oldest entries."""
    try:
        entries = sorted(THUMBNAIL_CACHE_DIR.glob('*.jpg'), key=lambda entry: entry.stat().st_mtime)
        for entry in entries[:max(len(entries) - THUMBNAIL_CACHE_MAX_FILES, 0)]:
            entry.unlink(missing_ok=True)
    except OSError:
        pass


def _decode_thumbnail(path: str, state: Any) -> np.ndarray:
    raw = is_raw_file(path)
    fast = _embedded_raw_thumbnail(path) if raw else _fast_image_thumbnail(path)
    if fast is not None:
        return fast
    image = gui_controller.resize_for_preview(load_source_image(path, state, half_size=raw), THUMBNAIL_LONG_EDGE)
    preview = gui_controller.GuiController._prepare_input_color_preview_image(  # pylint: disable=protected-access
        image,
        input_color_space=state.input_image.io.input_color_space,
        apply_cctf_decoding=state.input_image.io.input_cctf_decoding,
    )
    return np.uint8(np.clip(preview, 0.0, 1.0) * 255)


def _fast_image_thumbnail(path: str) -> np.ndarray | None:
    """Downscaled decode of ordinary 8-bit files; others take the full pipeline."""
    from PIL import Image, UnidentifiedImageError

    if Path(path).suffix.lower() == '.exr':
        return None
    try:
        with Image.open(path) as image:
            if image.mode not in ('RGB', 'RGBA', 'L', 'P'):
                return None
            image.thumbnail((THUMBNAIL_LONG_EDGE, THUMBNAIL_LONG_EDGE))
            return np.asarray(image.convert('RGB'), dtype=np.uint8)
    except (OSError, ValueError, UnidentifiedImageError):
        return None


def _embedded_raw_thumbnail(path: str) -> np.ndarray | None:
    import io

    from PIL import Image
    import rawpy

    # LibRaw reports orientation separately; embedded previews are stored unrotated.
    orientation = {3: Image.Transpose.ROTATE_180, 5: Image.Transpose.ROTATE_90, 6: Image.Transpose.ROTATE_270}
    try:
        with rawpy.imread(path) as raw:
            flip = raw.sizes.flip
            thumbnail = raw.extract_thumb()
            if thumbnail.format == rawpy.ThumbFormat.BITMAP:
                image = Image.fromarray(thumbnail.data)
            else:
                image = Image.open(io.BytesIO(thumbnail.data)).convert('RGB')
            image.thumbnail((THUMBNAIL_LONG_EDGE, THUMBNAIL_LONG_EDGE))
    except (OSError, ValueError, rawpy.LibRawError):
        return None
    if flip in orientation:
        image = image.transpose(orientation[flip])
    return np.asarray(image, dtype=np.uint8)


class BatchSignals(QObject):
    thumbnail_ready = Signal(str, object)
    prerendered = Signal(object)
    loaded = Signal(int, str, object)
    load_failed = Signal(int, str, str)
    item_rendered = Signal(int, object)
    item_failed = Signal(int, str)
    progress = Signal(int, int)
    finished = Signal(object)


class ThumbnailWorker(QRunnable):
    def __init__(self, paths: list[str], state: Any):
        super().__init__()
        self._paths = paths
        self._state = state
        self._cancel = threading.Event()
        self.signals = BatchSignals()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        for path in self._paths:
            if self._cancel.is_set():
                return
            try:
                thumbnail = extract_thumbnail(path, self._state)
            except Exception:  # pylint: disable=broad-exception-caught - one bad file must not stop the rest
                continue
            self.signals.thumbnail_ready.emit(path, thumbnail)
        prune_thumbnail_cache()


@dataclass(frozen=True, slots=True)
class LoadedPhoto:
    image: np.ndarray
    preview: np.ndarray | None
    is_proxy: bool


class LoadWorker(QRunnable):
    """Decodes one photo off the GUI thread; stale requests are skipped.

    Browsing decodes RAW files at half size. With ``full=True`` the complete
    image is read instead, for a scan.
    """

    def __init__(self, token: int, path: str, state: Any, is_current: Callable[[int], bool], *, full: bool = False):
        super().__init__()
        self._token = token
        self._path = path
        self._state = state
        self._is_current = is_current
        self._full = full
        self.signals = BatchSignals()

    def run(self) -> None:
        if not self._is_current(self._token):
            return
        try:
            self.signals.loaded.emit(self._token, self._path, self._load())
        except Exception as exc:  # pylint: disable=broad-exception-caught - reported to the user
            self.signals.load_failed.emit(self._token, self._path, f'{type(exc).__name__}: {exc}')

    def _load(self) -> LoadedPhoto:
        if self._full:
            return LoadedPhoto(load_source_image(self._path, self._state), None, False)
        image, is_proxy = load_preview_source(self._path, self._state)
        max_size = self._state.gui_only.display.settings.preview_max_size
        return LoadedPhoto(image, gui_controller.resize_for_preview(image, max_size), is_proxy)


@dataclass(frozen=True, slots=True)
class PrerenderTarget:
    path: str
    quarter_turns: int
    preview: np.ndarray | None


@dataclass(frozen=True, slots=True)
class PrerenderedPhoto:
    path: str
    quarter_turns: int
    look_key: int
    source_key: tuple
    preview: np.ndarray
    result: gui_controller.runtime.CachedResult


class PrerenderWorker(QRunnable):
    """Prepares neighbouring photos in the background so stepping to them is instant."""

    def __init__(self, targets: list[PrerenderTarget], state: Any, params: Any):
        super().__init__()
        self._targets = targets
        self._state = state
        self._params = params
        self._cancel = threading.Event()
        self.signals = BatchSignals()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        state = self._state
        look_key = gui_controller.runtime.look_key(state)
        source_key = preview_source_key(state)
        max_size = state.gui_only.display.settings.preview_max_size
        self._params.settings.preview_mode = True
        simulator = None
        for target in self._targets:
            if self._cancel.is_set():
                return
            try:
                preview = target.preview
                if preview is None:
                    source, _is_proxy = load_preview_source(target.path, state)
                    preview = np.asarray(gui_controller.resize_for_preview(source, max_size), dtype=np.float32)
                if self._cancel.is_set():
                    return
                oriented = np.rot90(preview, k=target.quarter_turns) if target.quarter_turns else preview
                with gui_controller.runtime.SIMULATION_LOCK:
                    if simulator is None:
                        simulator = gui_controller.runtime_simulator(
                            gui_controller.digest_params(self._params, apply_stocks_specifics=False),
                        )
                    scan = np.asarray(simulator.process(np.double(oriented)))
                display, _status = gui_controller.GuiController._prepare_output_display_image(  # pylint: disable=protected-access
                    scan,
                    output_color_space=state.simulation.io.output_color_space,
                    use_display_transform=state.gui_only.display.use_display_transform,
                )
            except Exception:  # pylint: disable=broad-exception-caught - prerendering is only an optimization
                continue
            self.signals.prerendered.emit(PrerenderedPhoto(
                target.path, target.quarter_turns, look_key, source_key, preview,
                gui_controller.runtime.CachedResult(
                    np.asarray(display, dtype=np.uint8),
                    np.asarray(scan, dtype=np.float32),
                    state.simulation.io.output_color_space,
                    state.gui_only.display.use_display_transform,
                ),
            ))


class BatchWorker(QRunnable):
    """Runs a preview or full-resolution export over every item in a job."""

    def __init__(self, job: BatchJob, *, prepare_display: Callable[..., tuple[np.ndarray, str]] | None = None):
        super().__init__()
        self._job = job
        self._prepare_display = prepare_display or gui_controller.GuiController._prepare_output_display_image  # pylint: disable=protected-access
        self.signals = BatchSignals()

    def cancel(self) -> None:
        self._job.cancel.set()

    def run(self) -> None:
        job = self._job
        failures: list[tuple[str, str]] = []
        completed = 0
        total = len(job.items)
        try:
            job.params.settings.preview_mode = job.mode == 'preview'
            digested = gui_controller.digest_params(job.params, apply_stocks_specifics=False)
            simulator = gui_controller.runtime_simulator(digested)
        except Exception as exc:  # pylint: disable=broad-exception-caught - reported through the summary
            self.signals.finished.emit(BatchSummary(job.mode, 0, (('', f'{type(exc).__name__}: {exc}'),), False))
            return

        self.signals.progress.emit(0, total)
        for position, (index, item) in enumerate(job.items, start=1):
            if job.cancel.is_set():
                break
            try:
                if job.mode == 'preview':
                    self.signals.item_rendered.emit(index, self._render_preview(item, simulator))
                else:
                    self._export(item, simulator)
                completed += 1
            except Exception as exc:  # pylint: disable=broad-exception-caught - one bad file must not stop the rest
                message = f'{type(exc).__name__}: {exc}'
                failures.append((item.path, message))
                self.signals.item_failed.emit(index, message)
            self.signals.progress.emit(position, total)

        directory = job.options.directory if job.options is not None else None
        self.signals.finished.emit(BatchSummary(job.mode, completed, tuple(failures), job.cancel.is_set(), directory))

    def _render_preview(self, item: BatchItem, simulator: Any) -> np.ndarray:
        state = self._job.state
        key = preview_source_key(state)
        if item.preview_input is None or item.preview_key != key:
            source, _is_proxy = load_preview_source(item.path, state)
            max_size = state.gui_only.display.settings.preview_max_size
            item.preview_input = np.asarray(gui_controller.resize_for_preview(source, max_size))
            item.preview_key = key
        with gui_controller.runtime.SIMULATION_LOCK:
            scan = simulator.process(self._oriented(item.preview_input, item))
        display, _status = self._prepare_display(
            scan,
            output_color_space=state.simulation.io.output_color_space,
            use_display_transform=state.gui_only.display.use_display_transform,
        )
        return np.asarray(display, dtype=np.uint8)

    def _export(self, item: BatchItem, simulator: Any) -> None:
        state = self._job.state
        options = self._job.options
        source = self._oriented(load_source_image(item.path, state), item)
        with gui_controller.runtime.SIMULATION_LOCK:
            scan = np.asarray(simulator.process(source))[..., :3]
        workflow = state.simulation.workflow
        encoded = encode_for_saving(
            scan,
            source_color_space=state.simulation.io.output_color_space,
            saving_color_space=workflow.saving_color_space,
            saving_cctf_encoding=workflow.saving_cctf_encoding,
        )
        target = unique_output_path(options.directory, f'{Path(item.path).stem}{options.suffix}', options.extension)
        gui_controller.save_image_oiio(
            str(target),
            encoded,
            color_space=workflow.saving_color_space,
            cctf_encoding=workflow.saving_cctf_encoding,
        )
        try:
            gui_controller.write_image_metadata(
                str(target),
                gui_controller.read_image_metadata(item.path),
                saving_color_space=workflow.saving_color_space,
                saving_cctf_encoding=workflow.saving_cctf_encoding,
            )
        except Exception:  # pylint: disable=broad-exception-caught - metadata is best effort; the image is saved
            pass

    @staticmethod
    def _oriented(image: np.ndarray, item: BatchItem) -> np.ndarray:
        oriented = np.rot90(np.asarray(image), k=item.quarter_turns) if item.quarter_turns else image
        return np.double(oriented)
