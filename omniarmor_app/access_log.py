"""Gunicorn's access log, with reset and invite tokens hidden.

Used by the Dockerfile's gunicorn command (--logger-class). A plain access log
would write every password-reset link anyone opened to the server's output,
where the hosting dashboard keeps it.
"""
from gunicorn.glogging import Logger

from .redact import redact

class RedactingLogger(Logger):
    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        # Every text part, not only the request line: the referer header and the
        # raw environ copies ({raw_uri}e and friends) carry the same address.
        return {key: redact(value) if isinstance(value, str) else value for key, value in atoms.items()}
