"""Split YAML frontmatter from a Markdown body. Never raises on malformed YAML."""

from __future__ import annotations

from typing import Tuple

import yaml


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Return ``(frontmatter_dict, body)``.

    Tolerant: missing or malformed frontmatter yields ``({}, original_text)`` rather than
    raising — sidecars are human-authored and may be sparse.
    """
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return {}, body
    if not isinstance(data, dict):
        return {}, body
    return data, body
