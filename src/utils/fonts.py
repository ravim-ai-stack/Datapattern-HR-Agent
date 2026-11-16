"""Font loading helpers for the Pillow-rendered certificate and PDF fallback."""

import os

from PIL import ImageFont

from src.constants.constants import CERTIFICATE_FONT_CANDIDATES


def _load_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibribd.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _load_certificate_font(size, style="regular"):
    for path in CERTIFICATE_FONT_CANDIDATES.get(style, CERTIFICATE_FONT_CANDIDATES["regular"]):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _fit_certificate_font(draw, text, style, start_size, max_width, min_size=18):
    size = start_size
    while size > min_size:
        font = _load_certificate_font(size, style)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _load_certificate_font(min_size, style)
