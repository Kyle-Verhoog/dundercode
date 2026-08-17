"""Estimated air time of a line within its episode.

The transcript carries no timecodes, so a line's position is modelled from
the dialogue itself: every aired line costs a beat plus its words at a
speaking pace, and every scene change costs a gap standing in for the
action, cutaways and silence that carry no dialogue. The estimate is
therefore honest about ordering and proportion — the tenth of an episode a
quote falls in is about right — while any single timestamp can be off by
tens of seconds.

Deleted lines are excluded: they never aired, so they have no place on the
episode's clock, and counting them would push every later line's estimate
forward (deleted scenes are mostly appended after the aired ones).
"""

import functools
from typing import Dict, Optional

from . import data

# Constants are calibrated so the median episode lands near the ~21:30 of
# content in a 30-minute broadcast slot, and the double-length episodes come
# out near 42:00. Tune the pace, not the output: they are a speaking rate
# and two pauses, and they should stay recognisable as such.
_SECONDS_PER_WORD = 60.0 / 185.0  # 185 wpm — the show talks fast
_SECONDS_PER_LINE = 0.4  # beat between speakers
_SECONDS_PER_SCENE_CHANGE = 3.0  # transition plus wordless action


@functools.lru_cache(maxsize=None)
def _timeline(season: int, episode: int) -> Dict[int, float]:
    """Offset in seconds from the top of the episode, per aired line number."""
    offsets: Dict[int, float] = {}
    t = 0.0
    prev_scene: Optional[int] = None
    for line in data.get_lines_for_episode(season, episode):
        if line.deleted:
            continue
        if prev_scene is not None and line.scene != prev_scene:
            t += _SECONDS_PER_SCENE_CHANGE
        prev_scene = line.scene
        offsets[line.lineno] = t
        t += _SECONDS_PER_LINE + len(line.line.split()) * _SECONDS_PER_WORD
    return offsets


def estimate_offset(line: data.Line) -> Optional[float]:
    """Seconds into the episode the line is estimated to land, None if deleted."""
    return _timeline(line.season, line.episode).get(line.lineno)


def format_offset(seconds: float) -> str:
    """Render an offset as M:SS."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"
