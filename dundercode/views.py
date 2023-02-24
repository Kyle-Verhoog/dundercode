import time
from typing import List, Optional, Tuple

from .html import Html


def _fmt_chars(chars: List[str]):
    chars = [char.capitalize() for char in chars]
    return (
        "%s and %s" % (",".join(chars[:-1]), chars[-1]) if len(chars) > 1 else chars[0]
    )


def _base_page() -> Html:
    return Html(
        attrs={
            "direction": "ltr",
        }
    )


def _add_base_meta(h: Html) -> None:
    h.meta(**{"content": "text/html;charset=utf-8", "http-equiv": "Content-Type"})


def not_found() -> Html:
    h = _base_page()
    h.text("Page not found")
    return h


def index(title: str) -> Html:
    start_t = time.time_ns()
    h = _base_page()
    with h.tag("head"):
        _add_base_meta(h)
        with h.el("script"):
            h.text(
                """
function doSearch(query) {
    location.href = location.href + "search/" + query;
}
function searchInput(el) {
    if (event.key === 'Enter') {
        doSearch(el.value);
    }
}
function searchButton() {
    var el = document.getElementById("search-text");
    doSearch(el.value);
}
"""
            )
        with h.el("title"):
            h.text(title)
    with h.tag("body"):
        with h.tag("h1"):
            h.text(title)
        with h.tag("h3"):
            h.text("search for quote")
        with h.tag(
            "input",
            id="search-text",
            placeholder="quote",
            onkeydown="searchInput(this)",
        ):
            pass
        with h.tag("button", onclick="searchButton()"):
            h.text("search")
    with h.tag("footer"):
        with h.tag("small"):
            h.text(f"page rendered in {(time.time_ns() - start_t)/1e3}us")
    return h


def search(
    start_ns: int,
    title: str,
    query: str,
    results: List[Tuple[int, int, int, int, List[str], str]],
) -> Html:
    h = _base_page()

    with h.tag("head"):
        with h.tag("title"):
            h.text(f"{query} - {title}")
        _add_base_meta(h)
        h.meta(name="description", content="search results")
        h.meta(property="og:title", content=title)
        h.meta(property="og:type", content="website")
        h.meta(property="og:description", content="search results")
    with h.tag("body"):
        for lineno, season, ep, scene, chars, line in results:
            with h.tag("p"):
                with h.tag("a", href=f"/quote/{lineno}"):
                    h.text(f"{_fmt_chars(chars)} in S{season}E{ep}:")
            with h.tag("blockquote"):
                h.text(line)
        if not results:
            with h.tag("p"):
                h.text("no lines found 😭")
    with h.tag("footer"):
        with h.tag("small"):
            h.text(f"query completed in {(time.time_ns()-start_ns)/1e6}ms")
    return h


def quote(
    start_ns: int,
    title: str,
    season: int,
    episode: int,
    scene: int,
    lineno: int,
    chars: List[str],
    quote: str,
) -> Html:
    h = _base_page()
    title = f"S{season}E{episode} {_fmt_chars(chars)} quote - {title}"
    with h.tag("head"):
        with h.tag("title"):
            h.text(title)
        _add_base_meta(h)
        h.meta(name="description", content=quote)
        h.meta(property="og:title", content=title)
        h.meta(property="og:type", content="website")
        h.meta(property="og::author", content="")
        h.meta(property="og:article:section", content=f"S{season}E{episode}")
        h.meta(property="og:description", content=f"{quote}")
    with h.tag("body"):
        with h.tag("h2"):
            h.text(f"{_fmt_chars(chars)} (S{season}E{episode})")
        with h.tag("blockquote"):
            h.text(quote)
        with h.tag("a", href=f"/quote/{lineno-1}"):
            h.text("previous line")
        h.text(", ")
        with h.tag("a", href=f"/quote/{lineno+1}"):
            h.text("next line")
        h.text(", ")
        with h.tag("a", href=f"/scene/{season},{episode},{scene}"):
            h.text("scene")
    with h.tag("footer"):
        with h.tag("small"):
            h.text(f"query completed in {(time.time_ns()-start_ns)/1e6}ms")
    return h


def scene(
    start_ns: int,
    title: str,
    season: int,
    episode: int,
    scene: int,
    chars: List[str],
    prev_scene_href: Optional[str],
    next_scene_href: Optional[str],
    lines: List[Tuple[int, List[str], str]],
) -> Html:
    h = _base_page()
    title = f"S{season}E{episode} scene {scene} - {title}"
    description = f"{_fmt_chars(chars)} scene"
    with h.tag("head"):
        with h.tag("title"):
            h.text(title)
        _add_base_meta(h)
        h.meta(name="description", content=description)
        h.meta(property="og:title", content=title)
        h.meta(property="og:type", content="website")
        h.meta(property="og:description", content=description)
    with h.tag("body"):
        with h.tag("h2"):
            h.text(f"S{season}E{episode} scene {scene}")
        for lineno, chars, line in lines:
            with h.tag("p"):
                h.text(f"{_fmt_chars(chars)}: ")
                with h.tag("q"):
                    h.text(f"{line}")
                with h.tag("sup"):
                    with h.tag("small"):
                        with h.tag("a", href=f"/quote/{lineno}"):
                            h.text("†")
        if prev_scene_href:
            with h.tag("a", href=prev_scene_href):
                h.text("previous scene")
        h.text(", ")
        if next_scene_href:
            with h.tag("a", href=next_scene_href):
                h.text("next scene")
    with h.tag("footer"):
        with h.tag("small"):
            with h.tag("a", href="/"):
                h.text(f"search")
            h.text(" | ")
            h.text(f"query completed in {(time.time_ns()-start_ns)/1e6}ms")
    return h
