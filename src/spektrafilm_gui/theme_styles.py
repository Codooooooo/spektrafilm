from __future__ import annotations

from pathlib import Path

from spektrafilm_gui.theme_palette import (
    ACCENT_FILL,
    ACCENT_FILL_HOVER,
    ACCENT_FILL_PRESSED,
    ACCENT_TINT,
    BASE_BG,
    BUTTON_BG,
    BUTTON_BG_HOVER,
    BUTTON_BG_PRESSED,
    CHECKED_BG,
    CONTROL_BG,
    CONTROL_BORDER,
    CONTROL_BORDER_FOCUS,
    CONTROL_BORDER_HOVER,
    CONTROL_MENU_BG,
    DISABLED_BG,
    FONT_FAMILY,
    FONT_SIZE,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_SEMIBOLD,
    HEADER_BG,
    PANEL_BG,
    RADIUS_ACTION,
    RADIUS_CARD,
    RADIUS_CONTROL,
    RADIUS_MENU_ITEM,
    SCROLLBAR_HANDLE_BG,
    SCROLLBAR_HANDLE_BG_HOVER,
    SECTION_CARD_BG,
    SIZE_ACTION_MIN_HEIGHT,
    SIZE_BUTTON_MIN_HEIGHT,
    SIZE_BUTTON_PADDING,
    SIZE_CHECKBOX_INDICATOR,
    SIZE_CHECKBOX_SPACING,
    SIZE_COMBO_DROPDOWN_WIDTH,
    SIZE_COMPACT_BUTTON_MIN_HEIGHT,
    SIZE_CONTROL_MIN_HEIGHT,
    SIZE_CONTROL_PADDING,
    SIZE_FOOTER_MIN_HEIGHT,
    SIZE_FORM_LABEL_MIN_WIDTH,
    SIZE_HEADER_PADDING,
    SIZE_SCROLLBAR_HANDLE_MIN,
    SIZE_SCROLLBAR_THICKNESS,
    SIZE_SPLITTER_HANDLE_MARGIN_LEFT,
    SIZE_SPLITTER_HANDLE_WIDTH,
    SIZE_SPIN_BUTTON_WIDTH,
    SIZE_TAB_MARGIN_RIGHT,
    SIZE_TAB_PADDING,
    SIZE_TAB_STRIP_OFFSET,
    SIZE_TOOLBUTTON_PADDING,
    SIZE_TOOLBUTTON_POPUP_PADDING_RIGHT,
    STATUS_BG,
    TAB_HOVER_BG,
    TAB_SELECTED_BG,
    TAB_TEXT_ACCENT,
    TEXT_BRIGHT,
    TEXT_CONTROL,
    TEXT_HEADER,
    TEXT_HEADER_SECTION,
    TEXT_ON_ACCENT,
    TEXT_PRIMARY,
    TEXT_SECTION_TITLE,
    TEXT_SELECTION_BG,
    TEXT_SOFT,
    TEXT_STATUS,
    TOOLTIP_BG,
)

_CHEVRON_DOWN_URL = (Path(__file__).parent / 'assets' / 'chevron-down.svg').as_posix()


def join_style_sections(*sections: str) -> str:
    return '\n\n'.join(section.strip() for section in sections if section.strip())


WINDOW_STYLE = f"""
QMainWindow {{
    background: {BASE_BG};
    color: {TEXT_PRIMARY};
}}

QWidget#appCentral {{
    background: {BASE_BG};
}}

QWidget {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE};
}}

QFrame#sidebarPanel {{
    background: {PANEL_BG};
    border: none;
    border-radius: {RADIUS_CARD};
}}

QFrame#viewerPanel {{
    background: transparent;
    border: none;
}}

QFrame {{
    background: transparent;
    border: none;
}}

QWidget#sectionCard {{
    background: {SECTION_CARD_BG};
    border-radius: {RADIUS_CARD};
}}

QWidget#sectionCard QFrame QLabel {{
    min-width: {SIZE_FORM_LABEL_MIN_WIDTH};
    color: {TEXT_SOFT};
}}

QLabel#sidebarEyebrow {{
    color: {TEXT_HEADER};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    letter-spacing: 0.08em;
    text-transform: lowercase;
}}

QToolTip {{
    background: {TOOLTIP_BG};
    color: {TEXT_BRIGHT};
    border: 1px solid {CONTROL_BORDER_HOVER};
    border-radius: {RADIUS_CONTROL};
    padding: 6px 8px;
}}
"""

TAB_STYLE = f"""
QTabWidget::pane,
QTabWidget#controlsTabWidget::pane {{
    border: none;
    background: transparent;
    top: {SIZE_TAB_STRIP_OFFSET};
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_SOFT};
    border: none;
    border-radius: {RADIUS_CONTROL};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    padding: {SIZE_TAB_PADDING};
    margin-right: {SIZE_TAB_MARGIN_RIGHT};
    min-height: {SIZE_CONTROL_MIN_HEIGHT};
}}

QTabBar::tab:hover {{
    background: {TAB_HOVER_BG};
    color: {TEXT_PRIMARY};
}}

QTabBar::tab:selected {{
    background: {TAB_SELECTED_BG};
    color: {TAB_TEXT_ACCENT};
}}

QToolButton[role="sectionToggle"] {{
    color: {TEXT_SECTION_TITLE};
    background: transparent;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    padding: 0;
    min-height: 0;
}}

QToolButton[role="sectionToggle"]:hover,
QToolButton[role="sectionToggle"]:pressed,
QToolButton[role="sectionToggle"]:checked {{
    background: transparent;
}}

QPushButton[role="accentAction"],
QPushButton[role="primaryAction"] {{
    min-height: {SIZE_ACTION_MIN_HEIGHT};
    border-radius: {RADIUS_ACTION};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QPushButton[role="accentAction"] {{
    color: {TEXT_BRIGHT};
}}

QPushButton[role="primaryAction"] {{
    background: {ACCENT_FILL};
    color: {TEXT_ON_ACCENT};
    font-weight: {FONT_WEIGHT_BOLD};
}}

QPushButton[role="primaryAction"]:hover {{
    background: {ACCENT_FILL_HOVER};
}}

QPushButton[role="primaryAction"]:pressed {{
    background: {ACCENT_FILL_PRESSED};
}}

QPushButton[role="primaryAction"]:disabled {{
    background: {DISABLED_BG};
    color: {TEXT_SOFT};
}}
"""

CONTROL_STYLE = f"""
QTextEdit,
QPlainTextEdit,
QListView,
QTreeView,
QMenu {{
    background: {CONTROL_BG};
    color: {TEXT_CONTROL};
    border: none;
    outline: none;
}}

QComboBox,
QLineEdit,
QAbstractSpinBox {{
    background: {CONTROL_BG};
    color: {TEXT_CONTROL};
    border: 1px solid {CONTROL_BORDER};
    border-radius: {RADIUS_CONTROL};
    min-height: {SIZE_CONTROL_MIN_HEIGHT};
    padding: {SIZE_CONTROL_PADDING};
    outline: none;
}}

QPushButton {{
    background: {BUTTON_BG};
    color: {TEXT_CONTROL};
    border: none;
    border-radius: {RADIUS_CONTROL};
    min-height: {SIZE_BUTTON_MIN_HEIGHT};
    padding: {SIZE_BUTTON_PADDING};
    text-align: center;
    outline: none;
}}

QPushButton[role="compactAction"] {{
    min-height: {SIZE_COMPACT_BUTTON_MIN_HEIGHT};
    padding: {SIZE_CONTROL_PADDING};
}}

QPushButton:hover {{
    background: {BUTTON_BG_HOVER};
    color: {TEXT_BRIGHT};
}}

QPushButton:pressed {{
    background: {BUTTON_BG_PRESSED};
}}

QPushButton:disabled {{
    background: {DISABLED_BG};
    color: {TEXT_SOFT};
}}

QComboBox:hover,
QLineEdit:hover,
QAbstractSpinBox:hover {{
    border-color: {CONTROL_BORDER_HOVER};
}}

QComboBox:focus,
QComboBox:on,
QLineEdit:focus,
QAbstractSpinBox:focus {{
    border-color: {CONTROL_BORDER_FOCUS};
}}

QPushButton:focus,
QToolButton:focus,
QCheckBox:focus,
QTabBar::tab:focus {{
    outline: none;
}}

QLineEdit,
QAbstractSpinBox,
QTextEdit,
QPlainTextEdit {{
    selection-background-color: {TEXT_SELECTION_BG};
    selection-color: {TEXT_BRIGHT};
}}

QLineEdit:read-only {{
    color: {TEXT_SOFT};
}}

QComboBox::drop-down {{
    border: none;
    width: {SIZE_COMBO_DROPDOWN_WIDTH};
    background: transparent;
}}

QComboBox::down-arrow {{
    image: url("{_CHEVRON_DOWN_URL}");
    width: 12px;
    height: 12px;
}}

QAbstractSpinBox::up-button,
QAbstractSpinBox::down-button {{
    background: transparent;
    border: none;
    width: {SIZE_SPIN_BUTTON_WIDTH};
    subcontrol-origin: border;
}}

QAbstractSpinBox::up-button:hover,
QAbstractSpinBox::down-button:hover,
QAbstractSpinBox::up-button:pressed,
QAbstractSpinBox::down-button:pressed {{
    background: transparent;
    border: none;
}}

QComboBox QAbstractItemView {{
    background: {CONTROL_MENU_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {CONTROL_BORDER_HOVER};
    border-radius: {RADIUS_CONTROL};
    padding: 4px;
    selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT_BRIGHT};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 0 6px;
    border-radius: {RADIUS_MENU_ITEM};
}}

QComboBox QAbstractItemView::item:selected {{
    background: {ACCENT_TINT};
    color: {TEXT_BRIGHT};
}}

QMenu {{
    background: {CONTROL_MENU_BG};
    border: 1px solid {CONTROL_BORDER_HOVER};
    border-radius: {RADIUS_CONTROL};
    padding: 4px;
}}

QMenu::item {{
    padding: 5px 16px;
    border-radius: {RADIUS_MENU_ITEM};
}}

QMenu::item:selected {{
    background: {ACCENT_TINT};
    color: {TEXT_BRIGHT};
}}

QAbstractItemView {{
    alternate-background-color: {BUTTON_BG};
    selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT_BRIGHT};
    border: none;
    outline: none;
}}

QHeaderView::section {{
    background: {HEADER_BG};
    color: {TEXT_HEADER_SECTION};
    border: none;
    padding: {SIZE_HEADER_PADDING};
}}

QCheckBox {{
    spacing: {SIZE_CHECKBOX_SPACING};
}}

QCheckBox::indicator {{
    width: {SIZE_CHECKBOX_INDICATOR};
    height: {SIZE_CHECKBOX_INDICATOR};
    border: none;
    background: {CONTROL_BG};
}}

QCheckBox::indicator:checked {{
    background: {CHECKED_BG};
}}

QCheckBox::indicator:checked:disabled,
QCheckBox::indicator:unchecked:disabled {{
    background: {DISABLED_BG};
}}

QToolButton {{
    background: transparent;
    border: none;
    padding: {SIZE_TOOLBUTTON_PADDING};
}}

QToolButton[popupMode="1"] {{
    padding-right: {SIZE_TOOLBUTTON_POPUP_PADDING_RIGHT};
}}
"""

WORKSPACE_STYLE = f"""
QFrame#appHeader {{
    background: {PANEL_BG};
    border-radius: {RADIUS_CARD};
    margin-bottom: 8px;
}}

QLabel#wordmark {{
    color: {TEXT_BRIGHT};
    font-size: 12pt;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QLabel#headerFile,
QLabel#stripProgress,
QLabel#dialogNote {{
    color: {TEXT_SOFT};
}}

QLabel#stripTitle,
QLabel#dialogHeading {{
    color: {TEXT_BRIGHT};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QLabel#dialogHeading {{
    font-size: 13pt;
}}

QLabel#stripEmpty {{
    color: {TEXT_SOFT};
    background: {CONTROL_BG};
    border: 1px dashed {CONTROL_BORDER_HOVER};
    border-radius: {RADIUS_ACTION};
}}

QFrame#batchStrip,
QFrame#folderPanel {{
    background: {PANEL_BG};
    border-radius: {RADIUS_CARD};
}}

QTreeView#folderTree {{
    background: transparent;
    border: none;
    color: {TEXT_PRIMARY};
    outline: none;
    selection-background-color: transparent;
    show-decoration-selected: 0;
}}

QTreeView#folderTree::item {{
    padding: 4px 2px;
    border-radius: {RADIUS_MENU_ITEM};
}}

QPushButton[role="toolAction"]:checked,
QPushButton[role="iconAction"]:checked {{
    background: {ACCENT_TINT};
}}

QFrame#stockCard {{
    background: {CONTROL_BG};
    border: 1px solid {CONTROL_BORDER};
    border-radius: {RADIUS_ACTION};
}}

QFrame#stockCard:hover {{
    border-color: {CONTROL_BORDER_HOVER};
}}

QWidget#sectionCard QFrame QLabel#stockKicker,
QWidget#sectionCard QFrame QLabel#stockDetail {{
    color: {TEXT_SOFT};
    font-size: 9pt;
}}

QWidget#sectionCard QFrame QLabel#stockName {{
    color: {TEXT_BRIGHT};
    font-size: 11pt;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QPushButton[role="stockStep"] {{
    background: transparent;
    min-height: 0;
    padding: 0;
    border-radius: {RADIUS_CONTROL};
}}

QPushButton[role="stockStep"]:hover {{
    background: {BUTTON_BG};
}}

QFrame#stockBrowser {{
    background: {PANEL_BG};
    border: 1px solid {CONTROL_BORDER_HOVER};
    border-radius: {RADIUS_CARD};
}}

QPushButton[role="chip"] {{
    background: transparent;
    color: {TEXT_SOFT};
    border: 1px solid {CONTROL_BORDER};
    border-radius: 13px;
    min-height: 18px;
    padding: 3px 12px;
}}

QPushButton[role="chip"]:hover {{
    color: {TEXT_BRIGHT};
    border-color: {CONTROL_BORDER_HOVER};
}}

QPushButton[role="chip"]:checked {{
    background: {ACCENT_TINT};
    color: {TEXT_BRIGHT};
    border-color: {ACCENT_FILL};
}}

QDialog#batchExportDialog {{
    background: {PANEL_BG};
}}

QListWidget#filmStrip {{
    background: transparent;
    border: none;
}}

QListWidget#filmStrip::item {{
    color: {TEXT_SOFT};
    border-radius: {RADIUS_ACTION};
    padding: 6px;
}}

QListWidget#filmStrip::item:hover {{
    background: {SECTION_CARD_BG};
}}

QListWidget#filmStrip::item:selected {{
    background: {ACCENT_TINT};
    color: {TEXT_BRIGHT};
}}

QPushButton[role="toolAction"],
QPushButton[role="primaryTool"] {{
    min-height: 22px;
    padding: 3px 12px;
    border-radius: {RADIUS_CONTROL};
}}

QPushButton[role="primaryTool"],
QDialogButtonBox QPushButton[role="primaryTool"] {{
    background: {ACCENT_FILL};
    color: {TEXT_ON_ACCENT};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QPushButton[role="primaryTool"]:hover {{
    background: {ACCENT_FILL_HOVER};
    color: {TEXT_ON_ACCENT};
}}

QPushButton[role="primaryTool"]:pressed {{
    background: {ACCENT_FILL_PRESSED};
}}

QPushButton[role="primaryTool"]:disabled {{
    background: {DISABLED_BG};
    color: {TEXT_SOFT};
}}

QPushButton[role="iconAction"] {{
    background: transparent;
    color: {TEXT_SOFT};
    padding: 0 10px;
}}

QPushButton[role="iconAction"]:hover {{
    background: {BUTTON_BG};
    color: {TEXT_BRIGHT};
}}

QProgressBar {{
    background: {CONTROL_BG};
    border: none;
    border-radius: 3px;
}}

QProgressBar::chunk {{
    background: {ACCENT_FILL};
    border-radius: 3px;
}}

QSlider::groove:horizontal {{
    background: {CONTROL_BORDER};
    height: 3px;
    border-radius: 1px;
}}

QSlider::sub-page:horizontal {{
    background: {ACCENT_FILL};
    height: 3px;
    border-radius: 1px;
}}

QSlider[bipolar="true"]::sub-page:horizontal {{
    background: {CONTROL_BORDER};
}}

QSlider::handle:horizontal {{
    background: {TEXT_BRIGHT};
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}

QSlider::handle:horizontal:hover {{
    background: {ACCENT_FILL_HOVER};
}}

QAbstractSpinBox#sliderValue {{
    background: transparent;
    border: 1px solid transparent;
    padding: 2px 4px;
}}

QAbstractSpinBox#sliderValue:hover {{
    border-color: {CONTROL_BORDER_HOVER};
}}

QAbstractSpinBox#sliderValue:focus {{
    background: {CONTROL_BG};
    border-color: {CONTROL_BORDER_FOCUS};
}}
"""

CHROME_STYLE = f"""
QSplitter::handle {{
    background: transparent;
    width: {SIZE_SPLITTER_HANDLE_WIDTH};
}}

QSplitter::handle:horizontal {{
    margin: 0 0 0 {SIZE_SPLITTER_HANDLE_MARGIN_LEFT};
}}

QScrollBar:vertical {{
    background: transparent;
    border: none;
    margin: 0;
    width: {SIZE_SCROLLBAR_THICKNESS};
}}

QScrollBar:horizontal {{
    background: transparent;
    border: none;
    margin: 0;
    height: {SIZE_SCROLLBAR_THICKNESS};
}}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_HANDLE_BG};
    border: 2px solid {PANEL_BG};
    border-radius: 5px;
    min-height: {SIZE_SCROLLBAR_HANDLE_MIN};
    min-width: {SIZE_SCROLLBAR_HANDLE_MIN};
}}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {{
    background: {SCROLLBAR_HANDLE_BG_HOVER};
}}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {{
    background: transparent;
    border: none;
    width: 0;
    height: 0;
}}

QGroupBox,
QDockWidget,
QToolBox,
QLabel,
QWidget[class="qt-scrollarea-viewport"] {{
    border: none;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QStatusBar {{
    background: {STATUS_BG};
    color: {TEXT_STATUS};
    border: none;
    border-radius: {RADIUS_CONTROL};
    min-height: {SIZE_FOOTER_MIN_HEIGHT};
}}

QStatusBar::item {{
    border: none;
}}
"""
