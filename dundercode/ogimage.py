"""Render quote cards as PNGs for link previews.

iMessage (LinkPresentation) and Google Messages never display
`og:description` — the image and the title are the only fields that
reach the recipient. So the quote is typeset into the image itself.
"""

import functools
import logging
import pathlib
from io import BytesIO
from typing import List, Tuple

import ddtrace
from PIL import Image, ImageDraw, ImageFont

from .dd import ddclient


logger = logging.getLogger(__name__)

WIDTH = 1200
HEIGHT = 630
_MARGIN = 90
_BG = (250, 247, 240)
_FG = (28, 28, 30)
_MUTED = (120, 118, 112)
_RULE = (214, 208, 196)

# Largest first: the quote is rendered at the biggest size that still fits
# inside the text box, so short quotes get big type and long ones shrink.
_QUOTE_SIZES = (86, 76, 66, 58, 50, 44, 38, 34, 30, 26)
_META_SIZE = 30
_MARK_SIZE = 26

# Fonts we can count on: macOS for local dev, DejaVu for the Docker image
# (installed via fonts-dejavu-core). Pillow's bundled default is the last
# resort so a missing font never takes the route down.
_FONT_CANDIDATES = {
    "regular": (
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
    "bold": (
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
}


@functools.lru_cache(maxsize=None)
def _font(weight: str, size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES[weight]:
        if pathlib.Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError as exc:
                logger.warning("could not load font %s: %s", path, exc)
    return ImageFont.load_default(size=size)


def _wrap(text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    """Greedy word wrap. Words wider than the box are hard-split."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while draw.textlength(word, font=font) > max_width and len(word) > 1:
            cut = len(word) - 1
            while cut > 1 and draw.textlength(word[:cut], font=font) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


def _line_height(font: ImageFont.ImageFont) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * 1.28)


def _fit_quote(
    text: str, max_width: int, max_height: int
) -> Tuple[ImageFont.ImageFont, List[str]]:
    """Pick the largest font size whose wrapped text fits the box."""
    lines: List[str] = []
    font = _font("regular", _QUOTE_SIZES[-1])
    for size in _QUOTE_SIZES:
        font = _font("regular", size)
        lines = _wrap(text, font, max_width)
        if len(lines) * _line_height(font) <= max_height:
            return font, lines
    # Even at the smallest size it overflows: clip and mark the elision.
    max_lines = max(1, max_height // _line_height(font))
    lines = lines[:max_lines]
    if lines:
        lines[-1] = lines[-1].rstrip(" ,.;:") + "…"
    return font, lines


@ddclient.traced(name="og_image")
def quote_card(quote: str, attribution: str, site: str = "dundercode") -> bytes:
    """Render *quote* as a 1200x630 PNG card and return the encoded bytes."""
    img = Image.new("RGB", (WIDTH, HEIGHT), _BG)
    draw = ImageDraw.Draw(img)

    meta_font = _font("bold", _META_SIZE)
    mark_font = _font("regular", _MARK_SIZE)
    footer_h = _line_height(meta_font) + _line_height(mark_font)
    box_w = WIDTH - 2 * _MARGIN
    box_h = HEIGHT - 2 * _MARGIN - footer_h - 40

    quote_font, lines = _fit_quote(f"“{quote}”", box_w, box_h)
    lh = _line_height(quote_font)

    # Vertically centre the quote in the space above the footer.
    y = _MARGIN + max(0, (box_h - len(lines) * lh) // 2)
    for line in lines:
        draw.text((_MARGIN, y), line, font=quote_font, fill=_FG)
        y += lh

    rule_y = HEIGHT - _MARGIN - footer_h - 24
    draw.line([(_MARGIN, rule_y), (WIDTH - _MARGIN, rule_y)], fill=_RULE, width=2)
    draw.text(
        (_MARGIN, HEIGHT - _MARGIN - footer_h), attribution, font=meta_font, fill=_FG
    )
    draw.text(
        (_MARGIN, HEIGHT - _MARGIN - _line_height(mark_font)),
        site,
        font=mark_font,
        fill=_MUTED,
    )

    span = ddtrace.tracer.current_span()
    if span is not None:
        span.set_tag("leash.unfurl.og_image.quote_len", len(quote))
        span.set_tag("leash.unfurl.og_image.lines", len(lines))
        span.set_tag("leash.unfurl.og_image.font_size", quote_font.size)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# In-process only: cards are 30-80KB each, so the cache is sized for memory
# rather than hit rate. Editing this module restarts the reloader and clears
# it, so it never hides a layout change the way a CDN copy would.
@functools.lru_cache(maxsize=256)
def cached_quote_card(quote: str, attribution: str) -> bytes:
    """`quote_card` memoised — the transcript is static, so cards are too."""
    return quote_card(quote, attribution)
