"""Keep one-time links out of logs.

A password-reset link carries its token in the path (/reset/<token>) and a team
invite carries one in the query (?invite=<token>). Anyone who can read a log
line holding either can use it, so everything that writes a request's address
somewhere lasting (the access log, the error log, the Autopilot error table)
passes it through redact() first.
"""
import re

_SECRETS = re.compile(
    r"(/reset/)[^/?#\s\"]+"
    r"|((?:^|[?&])(?:invite|token|code)=)[^&#\s\"]+",
    re.IGNORECASE,
)


def redact(text):
    """The same text with any reset or invite token replaced by [hidden]."""
    if not text:
        return text
    return _SECRETS.sub(lambda m: (m.group(1) or m.group(2)) + "[hidden]", str(text))
