"""Line icons for buttons and menu actions, drawn with QPainter.

Each icon is a 16×16 stroke drawing rendered in the colour of the button it
sits on (white on filled buttons, accent on tinted ones), so icons stay legible
on every button role and scale cleanly on high-DPI displays. The same drawing
code writes the small chevron and checkmark images used by the stylesheet.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

from . import gui_theme as theme

OPEN = "open"
SAVE = "save"
FOLDER = "folder"
RUN = "run"
STOP = "stop"
NEXT = "next"
APPLY = "apply"
CLEAR = "clear"
RELOAD = "reload"
INFO = "info"
WARNING = "warning"

# Icons that carry their own meaning in colour, whatever button they sit on.
_FIXED_COLOUR = {WARNING: theme.WARNING, INFO: theme.ACCENT}


def _folder_path(p):
    p.moveTo(1.75, 4.0)
    p.quadTo(1.75, 2.75, 3.0, 2.75)
    p.lineTo(6.0, 2.75)
    p.lineTo(7.5, 4.25)
    p.lineTo(13.0, 4.25)
    p.quadTo(14.25, 4.25, 14.25, 5.5)
    p.lineTo(14.25, 12.0)
    p.quadTo(14.25, 13.25, 13.0, 13.25)
    p.lineTo(3.0, 13.25)
    p.quadTo(1.75, 13.25, 1.75, 12.0)
    p.closeSubpath()


def _draw(painter, name, colour):
    pen = QPen(QColor(colour), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    p = QPainterPath()
    if name == FOLDER:
        _folder_path(p)
        p.moveTo(1.75, 6.5)
        p.lineTo(14.25, 6.5)
    elif name == OPEN:
        _folder_path(p)
        painter.drawPath(p)
        p = QPainterPath()
        p.moveTo(8.0, 11.25)
        p.lineTo(8.0, 7.0)
        p.moveTo(6.0, 9.0)
        p.lineTo(8.0, 7.0)
        p.lineTo(10.0, 9.0)
    elif name == SAVE:
        p.moveTo(8.0, 1.75)
        p.lineTo(8.0, 9.75)
        p.moveTo(5.0, 6.75)
        p.lineTo(8.0, 9.75)
        p.lineTo(11.0, 6.75)
        p.moveTo(2.25, 9.5)
        p.lineTo(2.25, 12.5)
        p.quadTo(2.25, 14.0, 3.75, 14.0)
        p.lineTo(12.25, 14.0)
        p.quadTo(13.75, 14.0, 13.75, 12.5)
        p.lineTo(13.75, 9.5)
    elif name == RUN:
        painter.setBrush(QColor(colour))
        p.moveTo(4.5, 2.75)
        p.lineTo(12.75, 8.0)
        p.lineTo(4.5, 13.25)
        p.closeSubpath()
    elif name == STOP:
        painter.setBrush(QColor(colour))
        p.addRoundedRect(QRectF(3.5, 3.5, 9.0, 9.0), 1.75, 1.75)
    elif name == NEXT:
        p.moveTo(2.5, 8.0)
        p.lineTo(13.0, 8.0)
        p.moveTo(9.0, 4.0)
        p.lineTo(13.0, 8.0)
        p.lineTo(9.0, 12.0)
    elif name == APPLY:
        painter.setPen(QPen(QColor(colour), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.moveTo(3.0, 8.5)
        p.lineTo(6.5, 12.0)
        p.lineTo(13.0, 4.5)
    elif name == CLEAR:
        p.moveTo(2.5, 4.25)
        p.lineTo(13.5, 4.25)
        p.moveTo(6.0, 4.25)
        p.lineTo(6.0, 2.75)
        p.lineTo(10.0, 2.75)
        p.lineTo(10.0, 4.25)
        p.moveTo(3.75, 4.25)
        p.lineTo(4.5, 13.25)
        p.lineTo(11.5, 13.25)
        p.lineTo(12.25, 4.25)
        p.moveTo(6.75, 6.75)
        p.lineTo(6.75, 10.75)
        p.moveTo(9.25, 6.75)
        p.lineTo(9.25, 10.75)
    elif name == RELOAD:
        p.arcMoveTo(QRectF(2.5, 2.5, 11.0, 11.0), 60)
        p.arcTo(QRectF(2.5, 2.5, 11.0, 11.0), 60, 300)
        painter.drawPath(p)
        p = QPainterPath()
        tip = QPointF(8.0 + 5.5 * 0.5, 8.0 - 5.5 * 0.866)
        p.moveTo(tip.x() - 3.2, tip.y() - 0.6)
        p.lineTo(tip)
        p.lineTo(tip.x() - 0.4, tip.y() + 3.1)
    elif name in (INFO, WARNING):
        painter.setBrush(QColor(colour))
        painter.setPen(Qt.PenStyle.NoPen)
        if name == INFO:
            p.addEllipse(QRectF(1.5, 1.5, 13.0, 13.0))
        else:
            p.moveTo(8.0, 1.75)
            p.lineTo(14.75, 13.75)
            p.lineTo(1.25, 13.75)
            p.closeSubpath()
        painter.drawPath(p)
        painter.setPen(QPen(QColor("#ffffff"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor("#ffffff"))
        if name == INFO:
            painter.drawLine(QPointF(8.0, 7.25), QPointF(8.0, 11.25))
            painter.drawPoint(QPointF(8.0, 4.9))
        else:
            painter.drawLine(QPointF(8.0, 6.0), QPointF(8.0, 9.25))
            painter.drawPoint(QPointF(8.0, 11.6))
        return
    painter.drawPath(p)


def _pixmap(name, colour, size, ratio, pad=0):
    """Square icon of ``size`` px, widened by ``pad`` px of empty space on each side."""
    pm = QPixmap(int((size + 2 * pad) * ratio), int(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(pad, 0)
    painter.scale(size / 16.0, size / 16.0)
    _draw(painter, name, colour)
    painter.end()
    return pm


def icon(name, colour=None):
    """Return the named icon drawn in ``colour`` (default: body text colour)."""
    colour = _FIXED_COLOUR.get(name, colour or theme.TEXT)
    disabled = _FIXED_COLOUR.get(name, theme.TEXT_TERTIARY)
    result = QIcon()
    # Square sizes serve menus and labels; the 22×16 variant matches the button
    # icon size set in the stylesheet and leaves a gap between icon and text.
    for size, pad in ((16, 0), (24, 0), (32, 0), (16, 3)):
        for ratio in (1.0, 2.0):
            for mode, tint in ((QIcon.Mode.Normal, colour), (QIcon.Mode.Active, colour), (QIcon.Mode.Disabled, disabled)):
                result.addPixmap(_pixmap(name, tint, size, ratio, pad), mode)
    return result


_ROLE_COLOUR = {"primary": "#ffffff", "success": "#ffffff", "tinted": theme.ACCENT_TEXT, "danger": theme.DANGER_TEXT}


def with_icon(widget, name):
    """Set the named icon on a button or action, in the colour of its role, and return it."""
    role = widget.property("role") if hasattr(widget, "property") else None
    widget.setIcon(icon(name, _ROLE_COLOUR.get(role)))
    return widget


# ---------------------------------------------------------------- stylesheet glyphs

def _glyph(kind, colour, path):
    img = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(colour), 3.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p = QPainterPath()
    if kind == "down":
        p.moveTo(8, 12); p.lineTo(16, 20); p.lineTo(24, 12)
    elif kind == "up":
        p.moveTo(8, 20); p.lineTo(16, 12); p.lineTo(24, 20)
    else:   # check
        p.moveTo(8, 16.5); p.lineTo(13.5, 22); p.lineTo(24, 10.5)
    painter.drawPath(p)
    painter.end()
    img.save(str(path), "PNG")


def stylesheet_glyphs():
    """Write the chevron and checkmark PNGs used by the stylesheet; return their paths (forward slashes)."""
    folder = Path(tempfile.gettempdir()) / "effsuite_gui_glyphs"
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, kind, colour in [("down", "down", theme.TEXT_SECONDARY), ("up", "up", theme.TEXT_SECONDARY),
                              ("down_disabled", "down", theme.TEXT_TERTIARY), ("up_disabled", "up", theme.TEXT_TERTIARY),
                              ("check", "check", "#ffffff")]:
        path = folder / f"{key}.png"
        try:
            _glyph(kind, colour, path)
        except Exception:
            pass   # temp folder not writable: combo/spin arrows and the checkmark are then not drawn
        out[key] = path.as_posix()
    return out
