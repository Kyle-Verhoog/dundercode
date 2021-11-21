import time
from typing import Optional, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from yattag import Doc

from . import data

app = FastAPI()


def _fmt_chars(chars: List[str]):
    return "%s and %s" % (",".join(chars[0:-1]), chars[-1]) if len(chars) > 1 else chars[0]


@app.get("/q/")
@app.get("/q/{query}")
async def root(
        query: str = "",
        char: Optional[str] = None,
        lineno: Optional[int] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        scene: Optional[int] = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ):
    start_t = time.time_ns()
    doc, tag, text = Doc().tagtext()

    if lineno is not None:
        try:
            line = data.get_line(lineno)
        except IndexError:
            pass
        else:
            with tag("p"):
                text(f"{_fmt_chars(line.speakers)} in S{line.season}E{line.episode}:")
            with tag("blockquote"):
                text(line.line)
            with tag("p"):
                with tag("a", href=f"/q/?lineno={lineno-1}"):
                    text("previous line")
                text(", ")
                with tag("a", href=f"/q/?lineno={lineno+1}"):
                    text("next line")
                text(", ")
                with tag("a", href=f"/q/?season={line.season}&episode={line.episode}&scene={line.scene}"):
                    text("scene")
    elif all(v is not None for v in (season, episode, scene)):
        for line in data.get_lines_for_scene(season, episode, scene):
            with tag("p"):
                text(_fmt_chars(line.speakers))
                text(": ")
                with tag("q"):
                    text(line.line)
        with tag("a", href=f"/q/?season={season}&episode={episode}&scene={scene-1}"):
            text("previous scene")
        text(", ")
        with tag("a", href=f"/q/?season={season}&episode={episode}&scene={scene+1}"):
            text("next scene")
    else:
        matches: List[data.Line] = []
        if start is not None and end is not None:
            try:
                lines = data.get_lines(start, end)
            except IndexError:
                pass
            else:
                matches += lines
        else:
            lines = data.find_lines(query, char)
            matches += lines

        for lineno, season, ep, scene, chars, line in matches:
            with tag("p"):
                with tag("a", href=f"/q/?lineno={lineno}"):
                    text(f"{_fmt_chars(chars)} in S{season}E{ep}:")
            with tag("blockquote"):
                text(line)

        if not matches:
            with tag("p"):
                text("no matching lines 😭")

    finish_t = time.time_ns()
    with tag("footer"):
        with tag("small"):
            text(f"query completed in {(finish_t-start_t)/1e6}ms")
    return HTMLResponse(doc.getvalue())
