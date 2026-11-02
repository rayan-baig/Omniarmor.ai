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

Whole log lines go through redact_line(), which also shortens every email
address to its first letter and domain: a line can quote the operator's
address, or an email error naming a customer's.
"""
import logging
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


# An email address, kept as its first letter and its domain: "p***@example.com".
# "%40" too: an address in a link's query is percent-encoded.
_EMAIL = re.compile(r"([A-Za-z0-9])[A-Za-z0-9._+-]*(@|%40)([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
# A Stripe Checkout id on its own, as in an error from Stripe's API.
_CHECKOUT_ID = re.compile(r"\bcs_(?:live|test)_[A-Za-z0-9]+")


def redact_line(text):
    """redact(), and also every email address shortened and any Stripe
    Checkout id hidden: for whole log lines, which can quote a person's
    address (an email that failed, the operator's own address) or an error
    from Stripe's API."""
    if not text:
        return text
    text = _EMAIL.sub(r"\1***\2\3", redact(text))
    return _CHECKOUT_ID.sub("cs_[hidden]", text)


class RedactingFilter(logging.Filter):
    """Runs every log line, with its traceback, through redact_line().

    Put on the handlers that write the server log (create_app does), so it
    covers OmniArmor's own lines, Flask's crash reports and the development
    server's access log alike.
    """

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # a broken log call: leave it as it is
            return True
        record.msg, record.args = redact_line(message), None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact_line(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_line(record.stack_info)
        return True
