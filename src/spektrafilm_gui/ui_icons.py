"""Stroke icons drawn locally so the toolbar never depends on an icon download."""

from __future__ import annotations

from functools import lru_cache

from qtpy import QtCore, QtGui, QtSvg

ICON_PATHS = {
    'rotate-ccw': 'M19.95 11a8 8 0 1 0 -.5 4m.5 5v-5h-5',
    'rotate-cw': 'M4.05 11a8 8 0 1 1 .5 4m-.5 5v-5h5',
    'fit': 'M4 8v-2a2 2 0 0 1 2-2h2 M4 16v2a2 2 0 0 0 2 2h2 M16 4h2a2 2 0 0 1 2 2v2 M16 20h2a2 2 0 0 0 2-2v-2',
    'plus': 'M12 5v14 M5 12h14',
    'chevron-left': 'M15 6l-6 6l6 6',
    'compare': 'M4 5h16v14h-16z M12 3v18',
    'search': 'M10 3a7 7 0 1 0 0 14a7 7 0 0 0 0 -14z M21 21l-6 -6',
    'chevron-right': 'M9 6l6 6l-6 6',
    'chevron-down': 'M6 9l6 6l6 -6',
    'folder': 'M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2',
    'grid': 'M4 4h6v6h-6z M14 4h6v6h-6z M4 14h6v6h-6z M14 14h6v6h-6z',
    'eye': 'M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0 M21 12c-2.4 4 -5.4 6 -9 6s-6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6s6.6 2 9 6',
    'export': 'M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2 M7 11l5 5l5 -5 M12 4v12',
    'close': 'M18 6l-12 12 M6 6l12 12',
    'trash': 'M4 7h16 M10 11v6 M14 11v6 M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12 M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3',
    'sliders': 'M4 6h8 M16 6h4 M14 4v4 M4 12h2 M10 12h10 M8 10v4 M4 18h11 M19 18h1 M17 16v4',
    'film': 'M4 4h16v16h-16z M8 4v16 M16 4v16 M4 8h4 M4 16h4 M4 12h16 M16 8h4 M16 16h4',
    'photo': 'M4 4h16v16h-16z M15 8h.01 M4 15l4 -4c.9 -.9 2.1 -.9 3 0l5 5 M14 14l1 -1c.9 -.9 2.1 -.9 3 0l2 2',
    'prism': 'M12 4l9 16h-18z M12 4v16',
    'settings': 'M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0 -8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M19 5l-2 2 M7 17l-2 2',
}
_RENDER_SIZE = 48
_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
    'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>'
)


@lru_cache(maxsize=None)
def ui_icon(name: str, color: str) -> QtGui.QIcon:
    svg = _SVG_TEMPLATE.format(color=color, path=ICON_PATHS[name])
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode('utf-8')))
    pixmap = QtGui.QPixmap(_RENDER_SIZE, _RENDER_SIZE)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QtGui.QIcon(pixmap)
