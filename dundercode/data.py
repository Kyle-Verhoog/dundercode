import functools
import re
from typing import (
    Callable,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
)

import ddtrace

from .crypt import decrypt
from .dd import ddclient


class Line(NamedTuple):
    lineno: int
    season: int
    episode: int
    scene: int
    speakers: List[str]
    line: str


def _read_data() -> List[Line]:
    data: List[Line] = []
    f = decrypt("transcript").decode("utf-8").strip()
    for lineno, entry in enumerate(f.split("\n")):
        split = entry.split(",")
        season, ep, scene = split[0:3]
        char, deleted = split[-2:]
        # Multi-speaker lines are written "Jim and Pam". Split on the
        # separator with its spaces — a bare "and" also matches inside
        # names like Brandon, Randy and Prince Grandfather.
        chars = char.split(" and ")
        # Keep the transcript's own casing: names are normalised in the
        # data, and lowercasing here would render 'AJ' as 'Aj' and
        # 'David Wallace' as 'David wallace'. Matching lowercases instead.
        chars = [c.strip() for c in chars]
        line = split[3:-2]
        line = ",".join(line).strip('"')
        data.append(Line(lineno, int(season), int(ep), int(scene), chars, line))
    return data


_lines: List[Line] = _read_data()


def get_line(ident: int) -> Line:
    return _lines[ident]


def get_lines(start: int, end: int) -> Iterable[Line]:
    return _lines[start:end]


def _lines_iter(matches: Callable[[Line], bool]) -> Generator[Line, None, None]:
    for line in _lines:
        if matches(line):
            yield line


def _characters() -> Set[str]:
    s = set()
    for line in _lines:
        s = s.union(set(line.speakers))
    return s


def get_lines_for_scene(season: int, episode: int, scene: int) -> Iterable[Line]:
    return _lines_iter(
        lambda l: l.scene == scene and l.episode == episode and l.season == season
    )


@functools.lru_cache(maxsize=None)
def get_scene_numbers(season: int, episode: int) -> Tuple[int, ...]:
    """Scene numbers that have lines in an episode, ascending.

    The transcript's scene numbering has holes — 47 numbers across 8
    episodes have no lines at all — so a scene's neighbours are not
    reliably ±1 and have to be looked up rather than computed.
    """
    return tuple(
        sorted(
            {l.scene for l in _lines if l.season == season and l.episode == episode}
        )
    )


def get_adjacent_scenes(
    season: int, episode: int, scene: int
) -> Tuple[Optional[int], Optional[int]]:
    """The previous and next scenes with lines, None past either end."""
    numbers = get_scene_numbers(season, episode)
    try:
        i = numbers.index(scene)
    except ValueError:
        return None, None
    return (
        numbers[i - 1] if i > 0 else None,
        numbers[i + 1] if i + 1 < len(numbers) else None,
    )


@ddclient.traced()
def find_lines(
    query_str: str, characters: Optional[Iterable[str]] = None
) -> List[Line]:
    """Search lines for *query_str*.

    Tokenises the query on whitespace and returns lines where every token
    appears (case-insensitively) in the line body or in a speaker name.
    All tokens must be present, order-independent; no regex surprises.
    """
    chars_in = characters if characters is not None else _characters()
    query_chars: Set[str] = {c.lower() for c in chars_in}
    tokens: List[str] = [t.lower().strip() for t in query_str.split() if t.strip()]

    span = ddtrace.tracer.current_span()
    if span is not None:
        span.set_tag("leash.search.query", query_str)
        span.set_tag("leash.search.tokens", len(tokens))
        span.set_tag("leash.search.strategy", "all_tokens")

    def _matches(line: Line) -> bool:
        speakers = [s.lower() for s in line.speakers]
        if not query_chars.intersection(speakers):
            return False
        if not tokens:
            return True
        haystacks = [line.line.lower(), *speakers]
        return all(any(tok in h for h in haystacks) for tok in tokens)

    matches = [line for line in _lines if _matches(line)]
    if span is not None:
        span.set_tag("leash.search.match_count", len(matches))
    return matches
