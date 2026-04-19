from contextlib import contextmanager
from html import escape as _html_escape

from .dd import ddclient


class Html:
    def __init__(self, attrs):
        self._page = {
            "type": "html",
            "attrs": attrs.copy(),
            "children": [],
        }
        self._cur_element = self._page

    # Elements whose text content is *not* HTML-escaped by the browser
    # (per the HTML spec); escaping would turn valid JS/CSS into garbage
    # like `if (a &lt; b)` or `document.getElementById(&quot;x&quot;)`.
    _RAW_TEXT_ELEMENTS = frozenset({"script", "style"})

    def _render(self, el, raw_text: bool = False) -> str:
        if isinstance(el, list):
            return "".join(self._render(e, raw_text) for e in el)
        elif isinstance(el, dict):
            attrs = " ".join(
                f'{k}="{_html_escape(str(v), quote=True)}"'
                for k, v in el["attrs"].items()
            )
            child_raw = raw_text or el["type"] in self._RAW_TEXT_ELEMENTS
            return f"""
<{el["type"]} {attrs}>
    {self._render(el["children"], child_raw)}
</{el["type"]}>
""".lstrip()
        elif isinstance(el, str):
            return el if raw_text else _html_escape(el)

    @ddclient.traced("render")
    def render(self) -> str:
        return f"""
<!DOCTYPE html>
{self._render(self._page)}
""".strip()

    def text(self, txt) -> None:
        if isinstance(self._cur_element, list):
            self._cur_element.append(txt)
        else:
            self._cur_element["children"].append(txt)

    @contextmanager
    def tag(self, el_type, **kwargs):
        el = {
            "type": el_type,
            "attrs": kwargs,
            "children": [],
        }
        prev = self._cur_element
        prev["children"].append(el)
        self._cur_element = el
        yield el
        self._cur_element = prev

    el = tag

    def meta(self, **kwargs):
        with self.tag("meta", **kwargs) as el:
            return el
