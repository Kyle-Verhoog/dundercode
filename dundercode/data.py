from typing import List, Tuple

from .crypt import decrypt

Dataset = List[
    Tuple[
        int,  # season
        int,  # episode
        int,  # scene
        List[str],  # speaker(s)
        str   # line
    ]
]


def _read_data() -> Dataset:
    data: Dataset = []

    f = decrypt("transcript").decode("utf-8").strip()
    for entry in f.split("\n"):
        split = entry.split(",")
        lineno, season, ep, scene = split[0:4]
        char, deleted = split[-2:]
        if "and" in char:
            chars = char.split("and")
        else:
            chars = [char]
        chars = [c.lower().strip() for c in chars]

        line = split[4:-2]
        line = ",".join(line).strip("\"")
        data.append((season, ep, scene, chars, line))
    return data


dataset = _read_data()
characters = set()
for season, ep, scene, chars, line in dataset:
    characters = characters.union(chars)
