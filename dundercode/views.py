from typing import List, Optional, Tuple

import ddtrace

from . import ogimage
from .html import Html


def fmt_chars(chars: List[str]):
    # Names arrive cased as the transcript has them ('AJ', 'David Wallace').
    return (
        "%s and %s" % (", ".join(chars[:-1]), chars[-1]) if len(chars) > 1 else chars[0]
    )


# iMessage and Google Messages render og:title and og:image but never
# og:description, so the quote has to lead the title. Long titles are cut
# by every client (Google Messages at ~36 chars); this keeps the quote
# readable while leaving room for the attribution suffix.
_OG_TITLE_QUOTE_MAX = 90


def _truncate(text: str, limit: int) -> str:
    """Trim *text* to *limit* chars on a word boundary, with an ellipsis."""
    if len(text) <= limit:
        return text
    head = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{head or text[:limit]}…"


def _base_page() -> Html:
    page = Html(
        attrs={
            "direction": "ltr",
        }
    )
    with page.tag("style"):
        page.text(
            """
body {
    margin: 0.5em;
    padding: 0;
}
        """
        )
    return page


def _add_base_meta(h: Html, description: str = "dundercode") -> None:
    h.meta(**{"content": "text/html;charset=utf-8", "http-equiv": "Content-Type"})
    h.meta(**{"name": "viewport", "content": "width=device-width, initial-scale=1.0"})
    # Exactly one name="description" per page: crawlers that fall back to it
    # take the first one they see.
    h.meta(**{"name": "description", "content": description})


def not_found() -> Html:
    h = _base_page()
    h.text("Page not found")
    return h


def index(title: str) -> Html:
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
            h.text("search for a quote")
        with h.tag(
            "input",
            id="search-text",
            placeholder="quote",
            onkeydown="searchInput(this)",
            autofocus="autofocus",
        ):
            pass
        with h.tag("button", onclick="searchButton()"):
            h.text("search")
    return h


def search(
    title: str,
    query: str,
    results: List[Tuple[int, int, int, int, List[str], str]],
    base_url: str = "",
) -> Html:
    h = _base_page()
    page_url = f"{base_url}/search/{query}"

    with h.tag("head"):
        with h.tag("title"):
            h.text(f"{query} - {title}")
        _add_base_meta(h, description="search results")
        h.meta(property="og:title", content=title)
        h.meta(property="og:type", content="website")
        h.meta(property="og:url", content=page_url)
        h.meta(property="og:description", content="search results")
        h.meta(property="og:image", content=f"{base_url}/og-image.png")
    with h.tag("body"):
        for lineno, season, ep, scene, chars, line in results:
            with h.tag("p"):
                with h.tag("a", href=f"/quote/{lineno}"):
                    h.text(f"{fmt_chars(chars)} in S{season}E{ep}:")
            with h.tag("blockquote"):
                h.text(line)
        if not results:
            with h.tag("p"):
                h.text("no lines found 😭")
    return h


def quote(
    title: str,
    season: int,
    episode: int,
    scene: int,
    lineno: int,
    chars: List[str],
    quote: str,
    scene_context: Optional[str] = None,
    base_url: str = "",
) -> Html:
    h = _base_page()
    speakers = fmt_chars(chars)
    page_title = f"S{season}E{episode} {speakers} quote - {title}"
    # The quote leads the title because that is the only text field every
    # client renders (iMessage and Google Messages both drop descriptions).
    short_quote = _truncate(quote, _OG_TITLE_QUOTE_MAX)
    og_title = f"“{short_quote}” — {speakers}, S{season}E{episode}"
    if short_quote != quote:
        # Title had to be cut: give clients that do show a description the
        # complete line rather than repeating the truncation.
        og_description = quote
    elif scene_context:
        og_description = scene_context
    else:
        og_description = f"The Office — S{season}E{episode}"
    page_url = f"{base_url}/quote/{lineno}"
    og_image = f"{base_url}/og/quote/{lineno}.png"

    span = ddtrace.tracer.current_span()
    if span is not None:
        span.set_tag("leash.unfurl.view", "quote")
        span.set_tag("leash.unfurl.og_title", og_title)
        span.set_tag("leash.unfurl.og_title_len", len(og_title))
        span.set_tag(
            "leash.unfurl.og_title_truncated", str(short_quote != quote).lower()
        )
        span.set_tag("leash.unfurl.og_description_len", len(og_description))
        span.set_tag("leash.unfurl.has_og_image", True)
        span.set_tag("leash.quote.has_scene_context", bool(scene_context))

    with h.tag("head"):
        with h.tag("title"):
            h.text(page_title)
        _add_base_meta(h, description=quote)
        h.meta(property="og:title", content=og_title)
        h.meta(property="og:type", content="article")
        h.meta(property="og:url", content=page_url)
        h.meta(property="og:description", content=og_description)
        h.meta(property="og:site_name", content=title)
        # The card image carries the quote as rendered text — it is what
        # iMessage and Google Messages actually show the recipient.
        h.meta(property="og:image", content=og_image)
        h.meta(property="og:image:type", content="image/png")
        h.meta(property="og:image:width", content=str(ogimage.WIDTH))
        h.meta(property="og:image:height", content=str(ogimage.HEIGHT))
        h.meta(property="og:image:alt", content=f"{speakers}: {short_quote}")
        h.meta(**{"name": "twitter:card", "content": "summary_large_image"})
        h.meta(**{"name": "twitter:title", "content": og_title})
        h.meta(**{"name": "twitter:description", "content": og_description})
        h.meta(**{"name": "twitter:image", "content": og_image})
    with h.tag("body"):
        with h.tag("h2"):
            h.text(f"{speakers} (S{season}E{episode})")
        if scene_context:
            with h.tag("p", style="color:#555;font-style:italic;margin:0 0 0.5em 0;"):
                with h.tag("small"):
                    h.text(f"Scene context: {scene_context}")
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
            with h.tag("a", href="/"):
                h.text(f"search")
    return h


def scene(
    title: str,
    season: int,
    episode: int,
    scene: int,
    chars: List[str],
    prev_scene_href: Optional[str],
    next_scene_href: Optional[str],
    lines: List[Tuple[int, List[str], str]],
    base_url: str = "",
) -> Html:
    h = _base_page()
    title = f"S{season}E{episode} scene {scene} - {title}"
    description = f"{fmt_chars(chars)} scene"
    page_url = f"{base_url}/scene/{season},{episode},{scene}"
    with h.tag("head"):
        with h.tag("title"):
            h.text(title)
        _add_base_meta(h, description=description)
        h.meta(property="og:title", content=title)
        h.meta(property="og:type", content="website")
        h.meta(property="og:url", content=page_url)
        h.meta(property="og:description", content=description)
        h.meta(property="og:image", content=f"{base_url}/og-image.png")
    with h.tag("body"):
        with h.tag("h2"):
            h.text(f"S{season}E{episode} scene {scene}")
        for lineno, chars, line in lines:
            with h.tag("p"):
                h.text(f"{fmt_chars(chars)}: ")
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
    return h
