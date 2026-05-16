import json
import logging
import os
import pathlib
import threading
from typing import Optional

import ddtrace
from openai import OpenAI

from . import data
from .dd import ddclient


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You explain scenes from the US version of The Office (the sitcom) to "
    "viewers who haven't watched the show. Given the lines of one scene, "
    "respond with one or two short sentences (max 50 words) describing what "
    "is happening, who the speakers are, and any context a newcomer would "
    "need to appreciate the humour. Do not quote the lines back. Do not "
    "include disclaimers or preamble."
)
_MODEL = os.environ.get("DUNDERCODE_OPENAI_MODEL", "gpt-4o-mini")
_CACHE_PATH = pathlib.Path(
    os.environ.get(
        "DUNDERCODE_SCENE_CACHE",
        pathlib.Path(__file__).parent.parent / "cache" / "scene_context.json",
    )
)

_cache_lock = threading.Lock()
_cache: Optional[dict] = None
_client: Optional[OpenAI] = None


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_CACHE_PATH, "r") as f:
            _cache = json.load(f)
    except FileNotFoundError:
        _cache = {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("scene context cache unreadable (%s); starting empty", exc)
        _cache = {}
    return _cache


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_PATH.with_suffix(_CACHE_PATH.suffix + ".tmp")
        with open(tmp, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, _CACHE_PATH)
    except OSError as exc:
        logger.warning("could not persist scene context cache: %s", exc)


def _get_client() -> Optional[OpenAI]:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    _client = OpenAI()
    return _client


def _format_scene(season: int, episode: int, scene: int) -> Optional[str]:
    lines = list(data.get_lines_for_scene(season=season, episode=episode, scene=scene))
    if not lines:
        return None
    body = "\n".join(
        f"{', '.join(s.capitalize() for s in line.speakers)}: {line.line}"
        for line in lines
    )
    return f"S{season}E{episode} scene {scene}:\n{body}"


@ddclient.workflow(name="scene_context")
def scene_context(season: int, episode: int, scene: int) -> Optional[str]:
    """Return a 1-2 sentence summary of an Office scene, or None.

    Cached on disk; the transcript is static, so each scene is summarised
    at most once. Returns None when no API key is configured or the call
    fails — callers should render the page without the blurb in that case.
    """
    key = f"{season},{episode},{scene}"
    span = ddtrace.tracer.current_span()

    with _cache_lock:
        cache = _load_cache()
        if key in cache:
            if span is not None:
                span.set_tag("leash.ai.scene_context.cache_hit", "true")
                span.set_tag("leash.ai.scene_context.scene", key)
            return cache[key]

    if span is not None:
        span.set_tag("leash.ai.scene_context.cache_hit", "false")
        span.set_tag("leash.ai.scene_context.scene", key)
        span.set_tag("leash.ai.scene_context.model", _MODEL)

    client = _get_client()
    if client is None:
        return None

    transcript = _format_scene(season, episode, scene)
    if transcript is None:
        return None

    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            max_tokens=120,
            temperature=0.4,
        )
    except Exception as exc:
        logger.warning("openai scene_context call failed: %s", exc)
        if span is not None:
            span.set_tag("leash.ai.scene_context.error", type(exc).__name__)
        return None

    summary = (resp.choices[0].message.content or "").strip()
    if not summary:
        return None

    if span is not None and resp.usage is not None:
        span.set_tag("leash.ai.scene_context.prompt_tokens", resp.usage.prompt_tokens)
        span.set_tag(
            "leash.ai.scene_context.completion_tokens", resp.usage.completion_tokens
        )

    with _cache_lock:
        cache = _load_cache()
        cache[key] = summary
        _save_cache(cache)

    return summary
