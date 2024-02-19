import logging
import os
import pathlib
from typing import Callable, Optional

from asgiref.typing import (
    ASGIReceiveCallable,
    ASGISendCallable,
    HTTPScope,
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
)
from datadog import DDASGIMiddleware

from . import pages
from . import views
from .dd import ddclient
from .html import Html

Handler = Callable[[HTTPScope], Html]
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(ddclient.LogHandler())
logger.addHandler(logging.StreamHandler())


def _load_static_assets():
    assets = {}
    path = pathlib.Path(__file__).parent.parent / "static"
    for filename in os.listdir(path):
        with open(path / filename, "rb") as f:
            assets[filename] = f.read()
    return assets


@ddclient.traced(name="route")
def _router(scope: HTTPScope) -> Optional[Handler]:
    if scope["path"] == "/":
        return pages.index
    elif scope["path"].startswith("/quote"):
        return pages.quote
    elif scope["path"].startswith("/search"):
        return pages.search
    elif scope["path"].startswith("/scene"):
        return pages.scene
    return None


def _serve_static(content_type: str, body: bytes) -> tuple[dict, dict]:
    return {
        "type": "http.response.start",
        "headers": [(b"Content-Type", content_type.encode("utf-8"))],
        "status": 200,
    }, {"type": "http.response.body", "body": body}


def _http_start(status: int) -> HTTPResponseStartEvent:
    return {
        "type": "http.response.start",
        "headers": [(b"Content-Type", b"text/html")],
        "status": status,
        "trailers": False,
    }


def _http_body(body: str) -> HTTPResponseBodyEvent:
    return {
        "type": "http.response.body",
        "body": body.encode("utf-8"),
        "more_body": False,
    }


async def application(
    scope: HTTPScope, receive: ASGIReceiveCallable, send: ASGISendCallable
):
    await receive()
    if scope["type"] == "http":
        if scope["path"] == "/favicon.ico":
            start, body = _serve_static("image/x-icon", static_assets["favicon.ico"])
            await send(start)
            await send(body)
            return

        route = _router(scope)
        if route is None:
            await send(_http_start(404))
            await send(_http_body(views.not_found().render()))
        else:
            await send(_http_start(200))
            await send(_http_body(route(scope).render()))
    else:
        raise NotImplementedError


static_assets = _load_static_assets()
app = DDASGIMiddleware(application)
