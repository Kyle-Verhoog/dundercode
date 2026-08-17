import logging
from typing import Optional

from asgiref.typing import HTTPScope

from . import ai
from . import data
from . import ogimage
from . import timing
from . import views
from .html import Html


logger = logging.getLogger(__name__)


class NotFound(Exception):
    """Raised by a handler when the request names something that isn't there.

    The application turns this into a 404. Handlers must raise it rather
    than letting an IndexError or ValueError escape, which the ASGI server
    can only answer with a dropped connection.
    """


def _base_url(scope: HTTPScope) -> str:
    scheme = scope.get("scheme", "https")
    headers = dict(scope.get("headers", []))
    host = headers.get(b"host", b"").decode("utf-8")
    if not host:
        server = scope.get("server")
        if server:
            host = f"{server[0]}:{server[1]}"
    return f"{scheme}://{host}"


def index(_: HTTPScope) -> Html:
    return views.index(title="dundercode")


def search(scope: HTTPScope):
    query = scope["path"][len("/search/") :]
    logger.info("using query %r", query)
    # Built explicitly rather than passing Lines through: the view unpacks
    # these positionally and a new field on Line would silently break it.
    results = [
        (l.lineno, l.season, l.episode, l.scene, l.speakers, l.line)
        for l in data.find_lines(query)
    ]
    return views.search(
        title="dundercode",
        query=query,
        results=results,
        base_url=_base_url(scope),
    )


def quote(scope: HTTPScope) -> Html:
    try:
        lineno = int(scope["path"][len("/quote/") :])
        if lineno < 0:  # negative indices would silently wrap to the tail
            raise NotFound
        line = data.get_line(lineno)
    except (ValueError, IndexError):
        raise NotFound
    context = ai.scene_context(
        season=line.season, episode=line.episode, scene=line.scene
    )
    return views.quote(
        title="dundercode",
        lineno=line.lineno,
        episode=line.episode,
        season=line.season,
        scene=line.scene,
        chars=line.speakers,
        quote=line.line,
        scene_context=context,
        offset_seconds=timing.estimate_offset(line),
        deleted=line.deleted,
        base_url=_base_url(scope),
    )


def quote_og_image(scope: HTTPScope) -> Optional[bytes]:
    """PNG card for `/og/quote/{lineno}.png`, or None if there's no such line."""
    ident = scope["path"][len("/og/quote/") : -len(".png")]
    try:
        lineno = int(ident)
        if lineno < 0:  # negative indices would silently wrap to the tail
            return None
        line = data.get_line(lineno)
    except (ValueError, IndexError):
        return None
    attribution = f"{views.fmt_chars(line.speakers)} — S{line.season}E{line.episode}"
    return ogimage.cached_quote_card(line.line, attribution)


def scene(scope: HTTPScope) -> Html:
    try:
        season, episode, scene = map(int, scope["path"][len("/scene/") :].split(","))
    except ValueError:  # wrong arity or non-numeric parts
        raise NotFound
    lines = list(data.get_lines_for_scene(season=season, episode=episode, scene=scene))
    if not lines:
        raise NotFound

    chars = set()
    _lines = []
    for line in lines:
        chars = chars.union(set(line.speakers))
        _lines.append((line.lineno, line.speakers, line.line))
    # Neighbours come from the scenes that exist, not scene±1: the
    # transcript's numbering has holes, and linking to one renders a
    # "previous scene" that leads nowhere.
    prev_scene, next_scene = data.get_adjacent_scenes(season, episode, scene)
    return views.scene(
        title="dundercode",
        season=season,
        episode=episode,
        scene=scene,
        chars=list(chars),
        lines=_lines,
        prev_scene_href=(
            f"/scene/{season},{episode},{prev_scene}" if prev_scene else None
        ),
        next_scene_href=(
            f"/scene/{season},{episode},{next_scene}" if next_scene else None
        ),
        base_url=_base_url(scope),
    )
