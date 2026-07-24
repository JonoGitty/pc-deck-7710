#!/usr/bin/env python3
"""The deck's 5x7 character ROM, for putting labels in an animation.

Reads core/font_rom.h — the generated table the firmware and the preview both
use — so text baked into a movie is the same glyphs the deck draws everywhere
else. Inventing a font here would be the giveaway that something was rendered
elsewhere and pasted in.
"""
import os
import re

_ROM = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "core", "font_rom.h")

LO, HI = 0x20, 0x7e


def _load():
    src = open(_ROM).read()
    block = src.split("FONT5_ASCII[FONT_ASCII_N][7] = {", 1)[1].split("};", 1)[0]
    # Strip comments first: the table annotates each row with the character it
    # is, so the entry for '{' carries a literal brace inside /* ... */ and
    # naive brace matching walks straight past the end of the row.
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    rows = re.findall(r"\{([^{}]*)\}", block)
    table = {}
    for i, body in enumerate(rows):
        vals = [int(v.strip(), 16) for v in body.split(",") if v.strip()]
        table[chr(LO + i)] = vals
    return table


FONT5 = _load()


def width(text, scale=1):
    return len(text) * 6 * scale


def draw(buf, w, h, x, y, text, level=3, scale=1):
    """Stamp text into a level buffer (bytes-like, w*h). Max-blend, like the
    deck's setDot: a glyph never dims what is already there."""
    cx = x
    for ch in text.upper():
        g = FONT5.get(ch) or FONT5["?"]
        for row in range(7):
            bits = g[row]
            for col in range(5):
                if not (bits & (0x10 >> col)):
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        px, py = cx + col * scale + sx, y + row * scale + sy
                        if 0 <= px < w and 0 <= py < h:
                            i = py * w + px
                            if level > buf[i]:
                                buf[i] = level
        cx += 6 * scale
    return cx - x


def centred(buf, w, h, y, text, level=3, scale=1):
    draw(buf, w, h, max(0, (w - width(text, scale)) // 2), y, text, level, scale)
