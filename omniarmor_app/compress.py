# -*- coding: utf-8 -*-
"""Smaller pages on the wire: gzip for HTML, CSS, JavaScript and JSON.

Pages and stylesheets are mostly repeated words and markup, so gzip makes
them 4 to 9 times smaller (the Academy map: 150 KB to 17 KB), which is most
of a first visit's wait on a slow phone connection. Caddy compresses for a
server of our own (Caddyfile), but on a host without it the app sent every
byte as it was. A proxy that compresses too sees the Content-Encoding and
leaves the response alone.

- Only when the browser says it takes gzip, only a complete 200 response
  over COMPRESS_MIN bytes, never a streamed one (the CSV exports start
  sending at once) and never twice.
- Static files are compressed once per file version and kept in memory.
- The forms' CSRF token is different on every page (security.csrf_token),
  so a compressed page gives away nothing about it (the BREACH attack).
"""

import gzip
import os
import threading

from flask import current_app, request

COMPRESS_MIN = 1024
LEVEL = 6
TYPES = {"text/html", "text/css", "text/plain", "text/csv", "text/javascript", "application/javascript",
         "application/json", "application/xml", "image/svg+xml", "application/manifest+json"}

_static = {}
_static_lock = threading.Lock()


def _takes_gzip():
    for part in request.headers.get("Accept-Encoding", "").lower().split(","):
        name, _, params = part.strip().partition(";")
        if name.strip() in ("gzip", "*"):
            return params.replace(" ", "") not in ("q=0", "q=0.0", "q=0.00", "q=0.000")
    return False


def _static_bytes(path):
    """A static file's gzip copy, made once per version of the file."""
    stat = os.stat(path)
    key = (path, stat.st_mtime_ns, stat.st_size)
    with _static_lock:
        found = _static.get(path)
        if found and found[0] == key:
            return found[1]
    with open(path, "rb") as f:
        packed = gzip.compress(f.read(), LEVEL, mtime=0)
    with _static_lock:
        _static[path] = (key, packed)
    return packed


def gzip_response(response):
    if (response.status_code != 200 or request.method == "HEAD" or response.mimetype not in TYPES
            or "Content-Encoding" in response.headers or "Content-Range" in response.headers):
        return response
    response.vary.add("Accept-Encoding")
    if not _takes_gzip():
        return response
    if request.endpoint == "static" and response.direct_passthrough:
        filename = (request.view_args or {}).get("filename", "")
        path = os.path.join(current_app.static_folder, filename)
        length = response.content_length or 0
        if length < COMPRESS_MIN or not os.path.isfile(path):
            return response
        packed = _static_bytes(path)
        response.response.close()
        response.direct_passthrough = False
        response.set_data(packed)
    elif response.is_streamed or response.direct_passthrough:
        return response
    else:
        data = response.get_data()
        if len(data) < COMPRESS_MIN:
            return response
        response.set_data(gzip.compress(data, LEVEL, mtime=0))
    response.headers["Content-Encoding"] = "gzip"
    etag, weak = response.get_etag()
    if etag:
        # The same file in another encoding: a weak validator still answers
        # "not modified" to the browser that has it.
        response.set_etag(etag, weak=True)
    return response
