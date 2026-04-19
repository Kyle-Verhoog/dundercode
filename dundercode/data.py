import functools
import re
from typing import Callable, Generator, Iterable, List, NamedTuple, Optional, Set

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
        if "and" in char:
            chars = char.split("and")
        else:
            chars = [char]
        chars = [c.lower().strip() for c in chars]
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


@ddclient.traced()
def find_lines(
    query_str: str, characters: Optional[Iterable[str]] = None
) -> List[Line]:
    """Search lines for *query_str*.

    Tokenises the query on whitespace and returns lines where every token
    appears (case-insensitively) in the line body or in a speaker name.
    All tokens must be present, order-independent; no regex surprises.
    """
    query_chars: Set[str] = set(characters) if characters is not None else _characters()
    tokens: List[str] = [t.lower().strip() for t in query_str.split() if t.strip()]

    span = ddtrace.tracer.current_span()
    if span is not None:
        span.set_tag("leash.search.query", query_str)
        span.set_tag("leash.search.tokens", len(tokens))
        span.set_tag("leash.search.strategy", "all_tokens")

    def _matches(line: Line) -> bool:
        if not query_chars.intersection(line.speakers):
            return False
        if not tokens:
            return True
        haystacks = [line.line.lower(), *line.speakers]
        return all(any(tok in h for h in haystacks) for tok in tokens)

    matches = [line for line in _lines if _matches(line)]
    if span is not None:
        span.set_tag("leash.search.match_count", len(matches))
    return matches
