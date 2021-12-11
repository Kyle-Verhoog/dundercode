from contextlib import contextmanager


class Html:
    def __init__(self, attrs):
        self._page = {
            "type": "html",
            "attrs": attrs.copy(),
            "children": [],
        }
        self._cur_element = self._page

    def _render(self, el) -> str:
        if isinstance(el, list):
            return "".join(self._render(e) for e in el)
        elif isinstance(el, dict):
            attrs = " ".join(f"{k}=\"{v}\"" for k, v in el["attrs"].items())
            return f"""
<{el["type"]} {attrs}>
    {self._render(el["children"])}
</{el["type"]}>
""".lstrip()
        elif isinstance(el, str):
            return el

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
