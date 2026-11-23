"""Qt standard icons for buttons and menu actions.

The style's own pixmaps are used instead of emoji so the icons follow the
platform theme and scale with the display. Actions without a standard
pixmap (edit, copy, materials) stay text-only.
"""
from PySide6.QtWidgets import QApplication, QStyle

_SP = QStyle.StandardPixmap
OPEN = _SP.SP_DialogOpenButton
SAVE = _SP.SP_DialogSaveButton
FOLDER = _SP.SP_DirIcon
RUN = _SP.SP_MediaPlay
STOP = _SP.SP_MediaStop
NEXT = _SP.SP_ArrowRight
APPLY = _SP.SP_DialogApplyButton
CLEAR = _SP.SP_TrashIcon
RELOAD = _SP.SP_BrowserReload
INFO = _SP.SP_MessageBoxInformation
WARNING = _SP.SP_MessageBoxWarning


def icon(pixmap):
    """Return the current style's icon for a QStyle.StandardPixmap."""
    return QApplication.style().standardIcon(pixmap)


def with_icon(widget, pixmap):
    """Set a standard icon on a button or action and return it."""
    widget.setIcon(icon(pixmap))
    return widget
