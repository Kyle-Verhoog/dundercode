import logging
from typing import Callable, Optional

from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, HTTPScope
from datadog import DDClient, DDConfig, DDASGIMiddleware

from . import pages
from . import views
from .html import Html

Handler = Callable[[HTTPScope], Html]
ddcfg = DDConfig(
    service="dundercode",
    tracing_enabled=True,
    version_use_git=True,
)
ddclient = DDClient(config=ddcfg)
logging.getLogger("").addHandler(ddclient.LogHandler())


def _router(scope) -> Optional[Handler]:
    if scope["path"] == "/":
        return pages.index
    elif scope["path"].startswith("/quote"):
        return pages.quote
    elif scope["path"].startswith("/search"):
        return pages.search
    elif scope["path"].startswith("/scene"):
        return pages.scene
    return None


async def application(scope: HTTPScope, receive: ASGIReceiveCallable, send: ASGISendCallable):
    await receive()
    if scope["type"] == "http":
        route = _router(scope)
        if route is None:
            await send({
                "type": "http.response.start",
                "headers": [(b"Content-Type", b"text/http")],
                "status": 404,
            })
            await send({"type": "http.response.body", "body": views.not_found().render().encode("utf-8")})
            return
        await send({
            "type": "http.response.start",
            "headers": [(b"Content-Type", b"text/html")],
            "status": 200,
        })
        await send({
            "type": "http.response.body",
            "body": route(scope).render().encode("utf-8"),
        })
    else:
        raise NotImplementedError


app = DDASGIMiddleware(application)
