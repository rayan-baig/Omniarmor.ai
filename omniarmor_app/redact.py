"""Keep one-time links out of logs.

A password-reset link carries its token in the path (/reset/<token>), a team
invite carries one in the query (?invite=<token>), and the return from Stripe
Checkout carries the checkout's id (?session_id=<id>), which the plan page
settles the payment with. Anyone who can read a log line holding one can use
it, so everything that writes a request's address somewhere lasting (the
access log, the error log, the Autopilot error table) passes it through
redact() first.

The same address also turns up percent-encoded inside another one: a signed
out visitor sent from the plan page to /login?next=%2Fapp%2Facademy%2Fplan
%3Fwelcome%3D1%26session_id%3D... carries the id in the sign-in page's log
line. The encoded spellings of "/", "?", "&" and "=" count as well.
"""
import re

# The query names whose values are secrets. Every name a route reads from its
# query string is either here or known to be harmless
# (tests/test_quiz_checks.py, TestTokensStayOutOfLogs).
SECRET_PARAMS = ("invite", "token", "code", "session_id")

_SECRETS = re.compile(
    r"((?:/|%2F)reset(?:/|%2F))[^/?#&%\s\"]+"
    r"|((?:^|[?&]|%3F|%26)(?:" + "|".join(SECRET_PARAMS) + r")(?:=|%3D))[^&#%\s\"]+",
    re.IGNORECASE,
)


def redact(text):
    """The same text with any reset or invite token replaced by [hidden]."""
    if not text:
        return text
    return _SECRETS.sub(lambda m: (m.group(1) or m.group(2)) + "[hidden]", str(text))
