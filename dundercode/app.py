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


def _serve_static(
    content_type: str, body: bytes, cache_control: Optional[str] = None
) -> tuple[dict, dict]:
    headers = [(b"Content-Type", content_type.encode("utf-8"))]
    if cache_control is not None:
        headers.append((b"Cache-Control", cache_control.encode("utf-8")))
    return {
        "type": "http.response.start",
        "headers": headers,
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
        if scope["path"] == "/og-image.png":
            start, body = _serve_static("image/png", static_assets["og-image.png"])
            await send(start)
            await send(body)
            return
        if scope["path"].startswith("/og/quote/") and scope["path"].endswith(".png"):
            card = pages.quote_og_image(scope)
            if card is not None:
                # Rendered fresh per request and explicitly not cacheable
                # while the card layout is still being iterated on — a card
                # cached by a client or crawler can't be re-checked.
                start, body = _serve_static(
                    "image/png", card, cache_control="no-store"
                )
                await send(start)
                await send(body)
                return
            await send(_http_start(404))
            await send(_http_body(views.not_found().render()))
            return

        route = _router(scope)
        body: Optional[str] = None
        if route is not None:
            try:
                # Render before the response starts. Sending the 200 first
                # leaves a handler failure no way out but a dropped
                # connection, which a browser shows as a blank page.
                body = route(scope).render()
            except pages.NotFound:
                body = None
        if body is None:
            await send(_http_start(404))
            await send(_http_body(views.not_found().render()))
        else:
            await send(_http_start(200))
            await send(_http_body(body))
    else:
        raise NotImplementedError


static_assets = _load_static_assets()
app = DDASGIMiddleware(application)
