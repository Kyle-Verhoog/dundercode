import time
from typing import Optional
import re

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from yattag import Doc

from . import data

app = FastAPI()


@app.get("/q/{query}")
async def root(query: str, char: Optional[str] = None):
    start = time.time_ns()
    query_expr = re.compile(query, re.IGNORECASE)
    query_chars = data.characters
    if char is not None:
        query_chars = set([c for c in data.characters if re.match(char, c)])

    matches = []

    for season, ep, scene, chars, line in data.dataset:
        if not set(chars).intersection(query_chars):
            continue
        if not query_expr.search(line):
            continue
        matches.append([season, ep, chars, line])

    doc, tag, text = Doc().tagtext()
    for season, ep, chars, line in matches:
        with tag("p"):
            chars_fmt = "%s and %s" % (",".join(chars[0:-1]), chars[-1]) if len(chars) > 1 else chars[0]
            text(f"{chars_fmt} in S{season}E{ep}:")
        with tag("blockquote"):
            text(line)

    text(f"searched for '{query}'")
    with tag("ul"):
        with tag("li"):
            text(f"with {len(query_chars)} characters")
        with tag("li"):
            text(f"with {len(matches)} matches")
        with tag("li"):
            finish = time.time_ns()
            text(f"in {(finish-start)/1e6}ms")
    if not matches:
        text("no results 😭")
    return HTMLResponse(doc.getvalue())
