import logging

from asgiref.typing import HTTPScope

from . import data
from . import views
from .html import Html


logger = logging.getLogger(__name__)


def index(_: HTTPScope) -> Html:
    return views.index(title="dundercode")


def search(scope: HTTPScope):
    query = scope["path"][len("/search/") :]
    logger.info("using query %r", query)
    results = list(data.find_lines(query))
    return views.search(
        title="dundercode",
        query=query,
        results=results,
    )


def quote(scope: HTTPScope) -> Html:
    lineno = int(scope["path"][len("/quote/") :])
    line = data.get_line(lineno)
    return views.quote(
        title="dundercode",
        lineno=line.lineno,
        episode=line.episode,
        season=line.season,
        scene=line.scene,
        chars=line.speakers,
        quote=line.line,
    )


def scene(scope: HTTPScope) -> Html:
    season, episode, scene = map(int, scope["path"][len("/scene/") :].split(","))
    lines = list(data.get_lines_for_scene(season=season, episode=episode, scene=scene))
    if lines:
        chars = set()
        _lines = []
        for line in lines:
            chars = chars.union(set(line.speakers))
            _lines.append((line.lineno, line.speakers, line.line))
        return views.scene(
            title="dundercode",
            season=season,
            episode=episode,
            scene=scene,
            chars=list(chars),
            lines=_lines,
            prev_scene_href=f"/scene/{season},{episode},{scene-1}",
            next_scene_href=f"/scene/{season},{episode},{scene+1}",
        )
    else:
        raise NotImplementedError
