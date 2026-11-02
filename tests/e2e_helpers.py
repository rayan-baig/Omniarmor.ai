"""Reads pages the way a browser does, so end-to-end tests fill in the real
forms (their fields, hidden CSRF token and buttons) instead of guessing them."""

import csv
import io
import re
from html.parser import HTMLParser


class Form:
    def __init__(self, attrs, section):
        self.action = attrs.get("action") or ""
        self.method = (attrs.get("method") or "get").lower()
        self.section = section      # id of the closest element with an id around the form
        self.inputs = []            # dicts of the input's attributes ("tag" says input, select or textarea)
        self.buttons = []           # dicts of submit buttons' attributes

    def fields(self, kind=None):
        return [i for i in self.inputs if kind is None or i.get("type", "text") == kind]

    def field(self, name):
        found = [i for i in self.inputs if i.get("name") == name]
        return found[0] if found else None

    def values(self):
        """What the browser would send before anyone types: hidden fields,
        filled boxes and checked boxes."""
        data = {}
        for i in self.inputs:
            name, kind = i.get("name"), i.get("type", "text")
            if not name or kind in ("submit", "button"):
                continue
            if kind in ("checkbox", "radio"):
                if "checked" in i:
                    data.setdefault(name, []).append(i.get("value", "on"))
                continue
            data[name] = i.get("value", "")
        return {k: (v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in data.items()}


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms, self.stack, self.form = [], [], None
        self.links, self.rows, self.row, self.cell = [], [], None, None

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if tag not in ("input", "br", "meta", "link", "img", "hr"):
            self.stack.append((tag, a.get("id")))
        if tag == "form":
            section = next((i for _, i in reversed(self.stack[:-1]) if i), None)
            self.form = Form(a, section)
            self.forms.append(self.form)
        elif tag in ("input", "select", "textarea") and self.form is not None:
            self.form.inputs.append({"tag": tag, **a})
        elif tag == "button" and self.form is not None:
            self.form.buttons.append(a)
        elif tag == "a" and "href" in a:
            self.links.append(a["href"])
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        for n in range(len(self.stack) - 1, -1, -1):
            if self.stack[n][0] == tag:
                del self.stack[n:]
                break
        if tag == "form":
            self.form = None
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def parse(html):
    p = _Parser()
    p.feed(html)
    p.close()
    return p


def forms(html):
    return parse(html).forms


def post_forms(html):
    return [f for f in forms(html) if f.method == "post"]


def table_rows(html):
    return parse(html).rows


def csv_rows(text):
    return list(csv.reader(io.StringIO(text)))


def flashes(html):
    return [" ".join(m.split()) for m in re.findall(r'<li class="flash[^"]*">(.*?)</li>', html, re.S)]
