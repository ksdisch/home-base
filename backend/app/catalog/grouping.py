"""Map a notebook to its home-screen group from template / tags / dir-name suffix."""

from __future__ import annotations

from typing import List, Optional

GROUP_LABELS = {
    "learning": "Learning",
    "interview-prep": "Interview prep",
    "custom": "Custom",
}
GROUP_ORDER = ["learning", "interview-prep", "custom"]


def group_for(
    template: Optional[str], tags: List[str], alias: Optional[str], dir_name: str
) -> str:
    tmpl = (template or "").lower()
    tagset = [str(t).lower() for t in (tags or [])]
    name = (alias or dir_name or "").lower()

    if (
        tmpl == "interview-prep"
        or "interview-prep" in tagset
        or "interview prep" in name
        or name.endswith("-interview-prep")
    ):
        return "interview-prep"
    # learning-topic, merged, archived-learning, or anything unknown -> Learning.
    return "learning"
