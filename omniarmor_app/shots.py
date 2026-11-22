# -*- coding: utf-8 -*-
"""Pictures of the app on the public pages (static/shots/): real screenshots
of the demo, with its pretend data, as small WebP files. The home page, the
Academy for schools page and each trade page show one beside the headline
and three under "How it works" (templates/_shots.html).

Each picture's width and height are read from its file, so the page keeps
their room while they load and nothing jumps.
"""

import functools
import os
import struct

from flask import current_app, url_for

# Which pictures a page shows: the one beside the headline, and the three
# steps. A trade page uses its own demo's; any other business page the
# restaurant's; a school's the classroom demo's.
TRADE_SHOTS = {"salons-and-barbershops": "salon", "tattoo-and-piercing-studios": "tattoo",
               "gyms-and-fitness-studios": "gym", "shops-and-retail-stores": "shop"}


@functools.lru_cache(maxsize=None)
def _size(path):
    """(width, height) of a WebP file, from its header; (0, 0) if unreadable."""
    try:
        with open(path, "rb") as f:
            head = f.read(30)
    except OSError:
        return 0, 0
    if head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        return 0, 0
    kind = head[12:16]
    if kind == b"VP8 ":
        w, h = struct.unpack("<HH", head[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        b = head[21:25]
        bits = int.from_bytes(b, "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X":
        return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    return 0, 0


def shot(name):
    """{src, width, height} for static/shots/<name>.webp."""
    w, h = _size(os.path.join(current_app.static_folder, "shots", f"{name}.webp"))
    return {"src": url_for("static", filename=f"shots/{name}.webp"), "width": w, "height": h}


def kind_for(trade_slug=None, school=False):
    """Which demo's pictures a page shows: "class", a trade's, or "biz"."""
    if school:
        return "class"
    return TRADE_SHOTS.get(trade_slug or "", "biz")
