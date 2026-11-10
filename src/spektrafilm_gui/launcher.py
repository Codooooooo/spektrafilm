"""Windowed desktop entry point.

Importing the GUI takes several seconds and ``pythonw`` has no console, so a
splash appears first and a startup failure is reported in a dialog and a log
file instead of the app silently not opening.
"""

from __future__ import annotations

import faulthandler
import os
from pathlib import Path
import sys
import traceback

from qtpy import QtCore, QtGui, QtWidgets

from spektrafilm_gui.theme_palette import PANEL_BG, TEXT_DIM, TEXT_HI

ICON_PATH = Path(__file__).parent / 'assets' / 'app-icon-arcs.ico'
LOG_PATH = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'spektrafilm' / 'spektrafilm.log'
APP_USER_MODEL_ID = 'spektrafilm.gui'
SPLASH_WIDTH = 420
SPLASH_HEIGHT = 220
SPLASH_ICON_SIZE = 96
SPLASH_FONT_FAMILIES = ['Segoe UI Variable Text', 'Segoe UI', 'Microsoft YaHei UI']


def _redirect_output_to_log() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG_PATH, 'w', encoding='utf-8', buffering=1)
    sys.stdout = log
    sys.stderr = log
    faulthandler.enable(file=log)


def _set_taskbar_identity() -> None:
    if sys.platform != 'win32':
        return
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


def _splash_font(pixel_size: int, weight: QtGui.QFont.Weight) -> QtGui.QFont:
    font = QtGui.QFont()
    font.setFamilies(SPLASH_FONT_FAMILIES)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def build_splash_pixmap(device_pixel_ratio: float) -> QtGui.QPixmap:
    pixmap = QtGui.QPixmap(int(SPLASH_WIDTH * device_pixel_ratio), int(SPLASH_HEIGHT * device_pixel_ratio))
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(PANEL_BG))
    painter.drawRoundedRect(QtCore.QRectF(0, 0, SPLASH_WIDTH, SPLASH_HEIGHT), 14, 14)

    icon_x = (SPLASH_WIDTH - SPLASH_ICON_SIZE) // 2
    QtGui.QIcon(str(ICON_PATH)).paint(painter, QtCore.QRect(icon_x, 28, SPLASH_ICON_SIZE, SPLASH_ICON_SIZE))

    painter.setPen(QtGui.QColor(TEXT_HI))
    painter.setFont(_splash_font(20, QtGui.QFont.Weight.DemiBold))
    painter.drawText(QtCore.QRect(0, 134, SPLASH_WIDTH, 32), QtCore.Qt.AlignCenter, 'spektrafilm')
    painter.setPen(QtGui.QColor(TEXT_DIM))
    painter.setFont(_splash_font(13, QtGui.QFont.Weight.Normal))
    painter.drawText(QtCore.QRect(0, 168, SPLASH_WIDTH, 26), QtCore.Qt.AlignCenter, '正在启动，请稍候……')
    painter.end()
    return pixmap


def _show_splash(app: QtWidgets.QApplication) -> QtWidgets.QSplashScreen:
    splash = QtWidgets.QSplashScreen(
        build_splash_pixmap(app.primaryScreen().devicePixelRatio()),
        QtCore.Qt.WindowStaysOnTopHint,
    )
    splash.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
    splash.setWindowTitle('spektrafilm 启动中')
    splash.show()
    app.processEvents()
    return splash


def _report_startup_failure(error: Exception) -> None:
    traceback.print_exc()
    QtWidgets.QMessageBox.critical(
        None,
        'spektrafilm 启动失败',
        f'程序没能启动。\n\n{type(error).__name__}: {error}\n\n详细信息见日志：\n{LOG_PATH}',
    )


def main() -> int:
    _redirect_output_to_log()
    _set_taskbar_identity()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(str(ICON_PATH)))
    splash = _show_splash(app)
    try:
        from spektrafilm_gui.app import main as run_gui

        run_gui(before_show=splash.close)
    except Exception as error:  # pylint: disable=broad-exception-caught - last resort before a silent exit
        splash.close()
        _report_startup_failure(error)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
