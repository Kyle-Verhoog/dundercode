import time

from asgiref.typing import HTTPScope

from . import data
from . import views
from .html import Html


def index(_: HTTPScope) -> Html:
    return views.index(title="dundercode")


def search(scope: HTTPScope):
    start_ns = time.time_ns()
    query = scope["path"][len("/search/"):]
    results = list(data.find_lines(query))
    return views.search(
        start_ns=start_ns,
        title="dundercode",
        query=query,
        results=results,
    )


def quote(scope: HTTPScope) -> Html:
    start_ns = time.time_ns()
    lineno = int(scope["path"][len("/quote/"):])
    line = data.get_line(lineno)
    return views.quote(
        start_ns=start_ns,
        title="dundercode",
        lineno=line.lineno,
        episode=line.episode,
        season=line.season,
        scene=line.scene,
        chars=line.speakers,
        quote=line.line,
    )


def scene(scope: HTTPScope) -> Html:
    start_ns = time.time_ns()
    season, episode, scene = map(int, scope["path"][len("/scene/"):].split(","))
    lines = list(data.get_lines_for_scene(season=season, episode=episode, scene=scene))
    if lines:
        chars = set()
        _lines = []
        for line in lines:
            chars = chars.union(set(line.speakers))
            _lines.append((line.lineno, line.speakers, line.line))
        return views.scene(
            start_ns=start_ns,
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
