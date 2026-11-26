"""Design tokens and the application stylesheet for the desktop GUI.

Widgets get their look from a ``role`` property (``set_role``) matched by
selectors in ``APP_STYLESHEET``, not from inline style strings, so every
colour, radius and spacing value is defined once here.
"""
from __future__ import annotations

# Light palette. Grey window, white cards, one blue accent; green is kept for
# the final Run button and the Material Editor Apply button, red for
# cancel/error only.
WINDOW = "#f5f5f7"
SURFACE = "#ffffff"
SURFACE_ALT = "#fafafc"       # alternate table rows, footers
FILL = "#ececf0"              # segmented-control track, disabled fields
FILL_HOVER = "#e3e3e8"
SEPARATOR = "#d8d8de"
HAIRLINE = "#e6e6eb"
CONTROL_BORDER = "#c9c9d0"

TEXT = "#1d1d1f"
TEXT_SECONDARY = "#5e5e66"    # 6.3:1 on white
TEXT_TERTIARY = "#8a8a92"     # placeholders and disabled text only

ACCENT = "#0a66d6"
ACCENT_HOVER = "#0b72ec"
ACCENT_PRESSED = "#0857b8"
ACCENT_TINT = "#e9f1fd"
ACCENT_TINT_HOVER = "#dce9fb"
ACCENT_TINT_PRESSED = "#cfe0f9"
ACCENT_TEXT = "#0a5bc2"

SUCCESS = "#1f8a3c"
SUCCESS_HOVER = "#23983f"
SUCCESS_PRESSED = "#1a7633"
SUCCESS_TINT = "#eaf6ed"
SUCCESS_TEXT = "#17692e"

DANGER_TINT = "#fdeeed"
DANGER_TINT_HOVER = "#fbe0de"
DANGER_TEXT = "#a3201c"

WARNING = "#c26a00"
WARNING_TINT = "#fff5e6"
WARNING_TEXT = "#8a4b00"

CONSOLE_BG = "#1c1c1e"
CONSOLE_TEXT = "#e8e8ed"

RADIUS_CONTROL = 6
RADIUS_BUTTON = 7
RADIUS_CARD = 10

FONT_STACK = '"Segoe UI Variable Text", "Segoe UI", -apple-system, system-ui, sans-serif'
MONO_STACK = '"Cascadia Mono", "Consolas", monospace'

# Matplotlib colours (charts and geometry drawings).
CHART_STANDARD = ACCENT
CHART_SAMPLE = "#d0461b"
CHART_GRID_ALPHA = 0.18


def set_role(widget, role):
    """Give a widget a stylesheet role and re-apply the style if it was already shown."""
    if widget.property("role") == role:
        return widget
    widget.setProperty("role", role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    return widget


def set_size(widget, size):
    """Mark a button as ``small`` (compact inline buttons)."""
    widget.setProperty("size", size)
    return widget


APP_STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    font-family: {FONT_STACK};
    font-size: 10pt;
}}
QWidget:disabled {{
    color: {TEXT_TERTIARY};
}}
QMainWindow, QDialog, QWidget#MaterialEditor {{
    background: {WINDOW};
}}
QToolTip {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    padding: 5px 8px;
}}

/* Menus */
QMenuBar {{
    background: {WINDOW};
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 5px;
    background: transparent;
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background: {FILL_HOVER};
}}
QMenu {{
    background: {SURFACE};
    border: 1px solid {SEPARATOR};
    padding: 4px;
}}
QMenu::item {{
    padding: 4px 16px 4px 10px;
    border-radius: 5px;
}}
QMenu::icon {{
    padding-left: 8px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QMenu::item:disabled {{
    color: {TEXT_TERTIARY};
}}
QMenu::separator {{
    height: 1px;
    background: {HAIRLINE};
    margin: 4px 8px;
}}
QToolBar {{
    background: {WINDOW};
    spacing: 6px;
    padding: 4px;
    border: none;
}}
QToolButton {{
    background: transparent;
    border-radius: 5px;
    padding: 4px;
}}
QToolButton:hover {{
    background: {FILL_HOVER};
}}
QToolButton:pressed, QToolButton:checked {{
    background: {SEPARATOR};
}}

/* Step tabs, drawn as a segmented control */
QTabWidget::pane {{
    border: none;
    background: {WINDOW};
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: {FILL};
    color: {TEXT_SECONDARY};
    padding: 6px 18px;
    margin: 4px 0 6px 0;
    border: 1px solid {FILL};
    font-weight: 500;
}}
QTabBar::tab:first {{
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    margin-left: 2px;
}}
QTabBar::tab:last, QTabBar::tab:only-one {{
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    background: {FILL_HOVER};
    border-color: {FILL_HOVER};
}}
QTabBar::tab:selected {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {CONTROL_BORDER};
    border-radius: 7px;
    font-weight: 600;
}}
QTabBar::tab:disabled {{
    color: {TEXT_TERTIARY};
}}
QDialog QTabWidget::pane {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS_CARD}px;
}}

/* Cards */
QGroupBox {{
    background-color: {SURFACE};
    font-weight: 600;
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS_CARD}px;
    margin-top: 24px;
    padding: 10px 12px 8px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px;
    top: 2px;
    padding: 0 2px;
    color: {TEXT_SECONDARY};
    background: transparent;
}}
QGroupBox:disabled::title {{
    color: {TEXT_TERTIARY};
}}

/* Tables and lists */
QHeaderView {{
    background: {SURFACE};
    border: none;
}}
QHeaderView::section {{
    background: {SURFACE};
    color: {TEXT_SECONDARY};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {SEPARATOR};
    border-right: 1px solid {HAIRLINE};
    font-weight: 600;
}}
QHeaderView::section:vertical {{
    border-bottom: 1px solid {HAIRLINE};
    padding: 2px 6px;
    font-weight: 500;
}}
QTableCornerButton::section {{
    background: {SURFACE};
    border: none;
    border-bottom: 1px solid {SEPARATOR};
}}
QAbstractItemView {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    outline: none;
}}
QAbstractItemView::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QTableWidget, QTableView {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    gridline-color: {HAIRLINE};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS_CARD}px;
}}
QComboBox QAbstractItemView, QListView {{
    background-color: {SURFACE};
    border: 1px solid {SEPARATOR};
    padding: 3px;
    outline: none;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QListView::item {{
    padding: 4px 8px;
    border-radius: 4px;
    background: transparent;
    color: {TEXT};
}}
QListView::item:hover {{
    background-color: {ACCENT_TINT};
    color: {TEXT};
}}
QListView::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}

/* Scroll areas and thin scroll bars */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget#PageBody {{
    background: {WINDOW};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: #c4c4cb;
    border-radius: 3px;
    min-height: 32px;
    margin: 0 2px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed {{
    background: #9a9aa2;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: #c4c4cb;
    border-radius: 3px;
    min-width: 32px;
    margin: 2px 0;
}}
QScrollBar::handle:horizontal:hover, QScrollBar::handle:horizontal:pressed {{
    background: #9a9aa2;
    margin: 0;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* Fields */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE};
    border: 1px solid {CONTROL_BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px 7px;
    min-height: 18px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: #a9a9b2;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {ACCENT};
    padding: 3px 6px;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {FILL};
    border-color: {HAIRLINE};
    color: {TEXT_TERTIARY};
}}
QAbstractItemView QLineEdit, QAbstractItemView QLineEdit:focus {{
    border: 1px solid {ACCENT};
    border-radius: 0px;
    padding: 0px 4px;
    min-height: 0px;
}}
QLineEdit[readOnly="true"] {{
    background-color: {SURFACE_ALT};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 18px;
    border: none;
}}
QComboBox::down-arrow {{
    image: url("__GLYPH_down__");
    width: 10px;
    height: 10px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    width: 16px;
    border: none;
    background: transparent;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    margin: 2px 2px 0 0;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    margin: 0 2px 2px 0;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {FILL};
    border-radius: 3px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("__GLYPH_up__");
    width: 8px;
    height: 8px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("__GLYPH_down__");
    width: 8px;
    height: 8px;
}}

/* Buttons. Feedback is on press (no transitions in Qt style sheets, so the
   pressed colour shows on the same frame as the mouse-down). */
QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {CONTROL_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    padding: 5px 13px;
    font-weight: 500;
    min-height: 18px;
    qproperty-iconSize: 22px 16px;
}}
QPushButton:hover {{
    background-color: {SURFACE_ALT};
    border-color: #a9a9b2;
}}
QPushButton:pressed {{
    background-color: {FILL_HOVER};
}}
QPushButton:focus {{
    border: 2px solid {ACCENT};
    padding: 4px 12px;
}}
QPushButton:disabled {{
    background-color: {FILL};
    border-color: {HAIRLINE};
    color: {TEXT_TERTIARY};
}}
QPushButton[role="primary"] {{
    background-color: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT};
    font-weight: 600;
    padding: 6px 16px;
}}
QPushButton[role="primary"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}
QPushButton[role="primary"]:focus, QPushButton[role="success"]:focus {{
    border: 2px solid #8ab8f2;
    padding: 5px 15px;
}}
QPushButton[role="success"] {{
    background-color: {SUCCESS};
    color: #ffffff;
    border: 1px solid {SUCCESS};
    font-weight: 600;
    padding: 6px 18px;
}}
QPushButton[role="success"]:hover {{
    background-color: {SUCCESS_HOVER};
    border-color: {SUCCESS_HOVER};
}}
QPushButton[role="success"]:pressed {{
    background-color: {SUCCESS_PRESSED};
    border-color: {SUCCESS_PRESSED};
}}
QPushButton[role="tinted"] {{
    background-color: {ACCENT_TINT};
    color: {ACCENT_TEXT};
    border: 1px solid {ACCENT_TINT};
    font-weight: 600;
}}
QPushButton[role="tinted"]:hover {{
    background-color: {ACCENT_TINT_HOVER};
    border-color: {ACCENT_TINT_HOVER};
}}
QPushButton[role="tinted"]:pressed {{
    background-color: {ACCENT_TINT_PRESSED};
    border-color: {ACCENT_TINT_PRESSED};
}}
QPushButton[role="tinted"]:focus {{
    border: 2px solid {ACCENT};
}}
QPushButton[role="danger"] {{
    background-color: {DANGER_TINT};
    color: {DANGER_TEXT};
    border: 1px solid {DANGER_TINT};
    font-weight: 600;
}}
QPushButton[role="danger"]:hover {{
    background-color: {DANGER_TINT_HOVER};
    border-color: {DANGER_TINT_HOVER};
}}
QPushButton[role="danger"]:pressed {{
    background-color: #f6cfcc;
}}
QPushButton[role="primary"]:disabled, QPushButton[role="success"]:disabled,
QPushButton[role="tinted"]:disabled, QPushButton[role="danger"]:disabled {{
    background-color: {FILL};
    border-color: {FILL};
    color: {TEXT_TERTIARY};
}}
QPushButton[size="small"] {{
    padding: 3px 9px;
    font-size: 9pt;
    min-height: 14px;
}}
QPushButton[size="small"]:focus {{
    padding: 2px 8px;
}}

/* Check boxes and radio buttons */
QCheckBox, QRadioButton {{
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #a9a9b2;
    background: {SURFACE};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url("__GLYPH_check__");
}}
QCheckBox::indicator:disabled {{
    background: {FILL};
    border-color: {HAIRLINE};
}}

/* Log console */
QPlainTextEdit {{
    background-color: {CONSOLE_BG};
    color: {CONSOLE_TEXT};
    border: none;
    border-radius: {RADIUS_CARD}px;
    padding: 8px 10px;
    font-family: {MONO_STACK};
    font-size: 9.5pt;
    selection-background-color: #3a5f99;
}}
/* Rich text (release notes) */
QTextBrowser {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS_CARD}px;
    padding: 6px 4px;
}}
QSplitter::handle:vertical {{
    background: transparent;
    height: 8px;
}}
QSplitter::handle:vertical:hover {{
    background: {SEPARATOR};
    border-radius: 2px;
    margin: 3px 40%;
}}
QStatusBar {{
    background: {WINDOW};
}}

/* Window chrome: top bar and page footers */
QFrame#TopBar {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#TopBar QLabel {{
    background: transparent;
}}
QFrame[role="vseparator"] {{
    background: {HAIRLINE};
    max-width: 1px;
    min-width: 1px;
    border: none;
    margin: 4px 2px;
}}
QFrame[role="hseparator"] {{
    background: {HAIRLINE};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QWidget#Page, QWidget#PageBody {{
    background: {WINDOW};
}}
QFrame#PageFooter {{
    background: {SURFACE_ALT};
    border-top: 1px solid {HAIRLINE};
}}
QFrame#StepBanner {{
    background: transparent;
    border: none;
}}

/* Notices (info / warning / danger / success) */
QFrame[notice="info"], QLabel[notice="info"] {{
    background: {ACCENT_TINT};
    border: none;
    border-radius: 8px;
    color: {ACCENT_TEXT};
}}
QFrame[notice="warning"], QLabel[notice="warning"] {{
    background: {WARNING_TINT};
    border: none;
    border-radius: 8px;
    color: {WARNING_TEXT};
}}
QFrame[notice="danger"], QLabel[notice="danger"] {{
    background: {DANGER_TINT};
    border: none;
    border-radius: 8px;
    color: {DANGER_TEXT};
}}
QFrame[notice="success"], QLabel[notice="success"] {{
    background: {SUCCESS_TINT};
    border: none;
    border-radius: 8px;
    color: {SUCCESS_TEXT};
}}
QFrame[notice="neutral"], QLabel[notice="neutral"] {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    color: {TEXT_SECONDARY};
}}
QLabel[notice] {{
    padding: 6px 10px;
}}
QFrame[notice] QLabel {{
    background: transparent;
    border: none;
}}

/* Text roles */
QLabel {{
    background: transparent;
}}
QLabel[role="pageTitle"] {{
    font-size: 15pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel[role="stepTitle"] {{
    font-size: 10.5pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel[role="secondary"] {{
    color: {TEXT_SECONDARY};
}}
QLabel[role="title"] {{
    font-size: 13pt;
    font-weight: 600;
}}
QLabel[role="caption"] {{
    color: {TEXT_SECONDARY};
    font-size: 9pt;
}}
QLabel[role="caption"]:disabled, QLabel[role="secondary"]:disabled {{
    color: {TEXT_TERTIARY};
}}
QLabel[role="fieldLabel"] {{
    color: {TEXT};
    font-weight: 400;
}}
QLabel[role="columnHeader"] {{
    color: {TEXT_SECONDARY};
    font-weight: 600;
    padding: 4px 2px;
}}
QLabel[role="chip"] {{
    color: {TEXT_SECONDARY};
    background: {FILL};
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 9pt;
}}
QLabel[role="status"] {{
    font-weight: 600;
    color: {TEXT};
}}
QLabel[role="helpText"] {{
    background: {SURFACE};
    padding: 14px 16px;
    font-size: 10pt;
}}
QComboBox::down-arrow:disabled, QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
    image: url("__GLYPH_down_disabled__");
}}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{
    image: url("__GLYPH_up_disabled__");
}}
"""


_stylesheet_cache = None


def app_stylesheet():
    """The application stylesheet with the chevron and checkmark images filled in."""
    global _stylesheet_cache
    if _stylesheet_cache is None:
        from .qt_icons import stylesheet_glyphs
        sheet = APP_STYLESHEET
        for key, path in stylesheet_glyphs().items():
            sheet = sheet.replace(f"__GLYPH_{key}__", path)
        _stylesheet_cache = sheet
    return _stylesheet_cache
