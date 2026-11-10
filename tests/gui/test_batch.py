from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
from qtpy import QtCore, QtTest, QtWidgets

from spektrafilm_gui import batch as batch_module
from spektrafilm_gui.batch import (
    encode_for_saving,
    is_raw_file,
    is_supported_file,
    photos_in_folder,
    unique_output_path,
)
from spektrafilm_gui.batch_panel import BatchStrip
from spektrafilm_gui.controller_runtime import fast_resize_for_preview
from spektrafilm_gui.widget_editors import SliderSpinEditor


@pytest.fixture(scope='module')
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize(
    ('name', 'raw', 'supported'),
    [
        ('a.CR3', True, True),
        ('a.rw2', True, True),
        ('a.JPG', False, True),
        ('a.exr', False, True),
        ('a.txt', False, False),
    ],
)
def test_file_type_detection(name, raw, supported) -> None:
    assert is_raw_file(name) is raw
    assert is_supported_file(name) is supported


def test_photos_in_folder_is_flat_filtered_and_naturally_sorted(tmp_path) -> None:
    for name in ('IMG_10.jpg', 'IMG_2.CR3', 'IMG_1.tif', 'notes.txt'):
        (tmp_path / name).touch()
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'IMG_0.jpg').touch()
    assert [Path(path).name for path in photos_in_folder(str(tmp_path))] == ['IMG_1.tif', 'IMG_2.CR3', 'IMG_10.jpg']


@pytest.mark.parametrize('shape', [(4000, 6000, 3), (6001, 4003, 3), (500, 700, 3)])
def test_fast_preview_resize_matches_the_requested_size(shape) -> None:
    image = np.full(shape, 0.25, dtype=np.float32)
    resized = fast_resize_for_preview(image, 640)
    scale = 640 / max(shape[:2])
    expected = (int(shape[0] * scale), int(shape[1] * scale), 3) if max(shape[:2]) > 640 else shape
    assert resized.shape == expected
    assert resized.dtype == image.dtype
    assert resized.mean() == pytest.approx(0.25)


def test_thumbnail_cache_round_trip_and_invalidation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(batch_module, 'THUMBNAIL_CACHE_DIR', tmp_path / 'cache')
    photo = tmp_path / 'photo.png'
    Image.fromarray(np.full((2000, 3000, 3), 200, dtype=np.uint8)).save(photo)

    first = batch_module.extract_thumbnail(str(photo), None)
    assert max(first.shape[:2]) == batch_module.THUMBNAIL_LONG_EDGE
    assert len(list((tmp_path / 'cache').glob('*.jpg'))) == 1

    monkeypatch.setattr(batch_module, '_decode_thumbnail', lambda *_args: pytest.fail('should use the cache'))
    assert batch_module.extract_thumbnail(str(photo), None).shape == first.shape

    monkeypatch.undo()
    monkeypatch.setattr(batch_module, 'THUMBNAIL_CACHE_DIR', tmp_path / 'cache')
    os.utime(photo, ns=(1, 1))
    batch_module.extract_thumbnail(str(photo), None)
    assert len(list((tmp_path / 'cache').glob('*.jpg'))) == 2


def test_unique_output_path_never_reuses_an_existing_file(tmp_path) -> None:
    assert unique_output_path(str(tmp_path), 'photo', '.jpg').name == 'photo.jpg'
    (tmp_path / 'photo.jpg').touch()
    (tmp_path / 'photo_2.jpg').touch()
    assert unique_output_path(str(tmp_path), 'photo', '.jpg').name == 'photo_3.jpg'


def test_encode_for_saving_keeps_matching_encoded_output() -> None:
    image = np.full((2, 2, 3), 0.5)
    encoded = encode_for_saving(
        image, source_color_space='sRGB', saving_color_space='sRGB', saving_cctf_encoding=True,
    )
    assert encoded is image


def test_slider_value_beyond_range_is_kept_by_the_number_box(qapp) -> None:
    editor = SliderSpinEditor(low=-5.0, high=5.0)
    editor.setMinimum(-100.0)
    editor.setMaximum(100.0)
    editor.value = 12.5
    assert editor.value == pytest.approx(12.5)
    assert editor._slider.value() == editor._SLIDER_STEPS


def test_slider_drag_reports_once_on_release(qapp) -> None:
    editor = SliderSpinEditor(low=0.0, high=2.0)
    editor.resize(300, 30)
    editor.show()
    qapp.processEvents()
    received: list[float] = []
    editor.valueChanged.connect(received.append)

    slider = editor._slider
    y = slider.height() // 2
    QtTest.QTest.mousePress(slider, QtCore.Qt.LeftButton, pos=QtCore.QPoint(20, y))
    for x in range(30, 170, 20):
        QtTest.QTest.mouseMove(slider, QtCore.QPoint(x, y))
        qapp.processEvents()
    assert received == []
    QtTest.QTest.mouseRelease(slider, QtCore.Qt.LeftButton, pos=QtCore.QPoint(170, y))
    qapp.processEvents()
    editor.close()

    assert len(received) == 1
    assert received[0] == pytest.approx(editor.value)
    assert editor.value > 0.5


def test_slider_double_click_returns_to_program_set_value(qapp) -> None:
    editor = SliderSpinEditor(low=0.0, high=2.0)
    editor.set_default(0.5)
    editor.value = 0.5
    editor.resize(300, 30)
    editor.show()
    qapp.processEvents()
    received: list[float] = []
    editor.valueChanged.connect(received.append)
    slider = editor._slider
    y = slider.height() // 2
    QtTest.QTest.mouseClick(slider, QtCore.Qt.LeftButton, pos=QtCore.QPoint(slider.width() - 30, y))
    qapp.processEvents()
    assert editor.value > 1.5

    handle_x = int(slider.width() * editor.value / 2.0)
    QtTest.QTest.mouseDClick(slider, QtCore.Qt.LeftButton, pos=QtCore.QPoint(handle_x, y))
    qapp.processEvents()
    editor.close()

    assert editor.value == pytest.approx(0.5)
    assert slider.value() == 250
    assert received[-1] == pytest.approx(0.5)


def test_format_chips_are_replaced_immediately(qapp) -> None:
    strip = BatchStrip()
    counts = {'RAW': 3, 'JPEG': 10}
    strip.set_format_counts(counts, '')
    strip.set_format_counts(counts, 'RAW')
    chips = [button for button in strip.findChildren(QtWidgets.QPushButton) if button.property('role') == 'chip']
    assert sorted(button.text() for button in chips) == ['JPEG 10', 'RAW 3', '全部 13']
    assert [button.text() for button in chips if button.isChecked()] == ['RAW 3']


def test_a_single_format_needs_no_filter_chips(qapp) -> None:
    strip = BatchStrip()
    strip.set_format_counts({'JPEG': 4}, '')
    assert not [button for button in strip.findChildren(QtWidgets.QPushButton) if button.property('role') == 'chip']


def test_setting_a_value_does_not_move_the_reset_target(qapp) -> None:
    editor = SliderSpinEditor(low=0.0, high=2.0)
    editor.set_default(0.5)
    editor.value = 1.5
    editor.reset_to_default()
    assert editor.value == pytest.approx(0.5)


def test_pressing_the_handle_without_moving_reports_nothing(qapp) -> None:
    editor = SliderSpinEditor(low=0.0, high=1.0)
    editor.value = 0.5
    editor.resize(300, 30)
    editor.show()
    qapp.processEvents()
    received: list[float] = []
    editor.valueChanged.connect(received.append)
    slider = editor._slider
    QtTest.QTest.mouseClick(slider, QtCore.Qt.LeftButton, pos=QtCore.QPoint(slider.width() // 2, slider.height() // 2))
    qapp.processEvents()
    editor.close()
    assert received == []
    assert editor.value == pytest.approx(0.5)


def test_slider_click_on_track_jumps_there(qapp) -> None:
    editor = SliderSpinEditor(low=0.0, high=1.0)
    editor.resize(300, 30)
    editor.show()
    qapp.processEvents()
    slider = editor._slider
    QtTest.QTest.mouseClick(slider, QtCore.Qt.LeftButton, pos=QtCore.QPoint(int(slider.width() * 0.75), slider.height() // 2))
    qapp.processEvents()
    editor.close()
    assert editor.value == pytest.approx(0.75, abs=0.06)
