"""Shared fixtures. Tests never touch the real data dir and never invoke the real nlm CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REAL_ROOT = Path.home() / "Projects" / "NotebookLMs"
needs_real_data = pytest.mark.skipif(
    not REAL_ROOT.exists(), reason="real NotebookLMs sidecar dir not present"
)


@pytest.fixture(autouse=True, scope="session")
def _isolate_data_dir(tmp_path_factory) -> None:
    """Point the hub's SQLite/cache at a throwaway dir for the whole test session."""
    data_dir = tmp_path_factory.mktemp("hub_data")
    os.environ["LEARNING_HUB_DATA"] = str(data_dir)
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def write_notebook(root: Path, dir_name: str, readme: str, artifact_map: str | None = None) -> Path:
    nb = root / dir_name
    nb.mkdir(parents=True, exist_ok=True)
    (nb / "README.md").write_text(readme, encoding="utf-8")
    if artifact_map is not None:
        (nb / "artifacts").mkdir(exist_ok=True)
        (nb / "artifacts" / "audio-series-artifact-map.json").write_text(
            artifact_map, encoding="utf-8"
        )
    return nb


# A full UUID helper for crafting fixtures.
def uid(seed: str) -> str:
    h = (seed + "0" * 32)
    hexs = "".join(c if c in "0123456789abcdef" else format(ord(c) % 16, "x") for c in h.lower())
    return f"{hexs[:8]}-{hexs[8:12]}-{hexs[12:16]}-{hexs[16:20]}-{hexs[20:32]}"


@pytest.fixture
def crafted_root(tmp_path: Path) -> Path:
    """A synthetic sidecar root packed with the adversarial cases the parser must survive."""
    root = tmp_path / "NotebookLMs"
    root.mkdir()

    # 1) Healthy notebook WITH artifact map; README audio table extends past the map (Eps 3-4),
    #    duplicate id across README+map must dedupe, and a Source table must NOT be ingested.
    nb1 = uid("nbone")
    a1, a2, a3, a4 = uid("aud1"), uid("aud2"), uid("aud3"), uid("aud4")
    q1, g1 = uid("quiz1"), uid("guide1")
    src = uid("source9")
    write_notebook(
        root,
        "alpha-learning",
        f"""---
notebook_id: {nb1}
alias: alpha-learning
title: Alpha Learning Topic
template: learning-topic
tags: [learning, alpha]
---

# Alpha Learning Topic
**NotebookLM:** https://notebooklm.google.com/notebook/{nb1}

## Sources
| # | Title | Type | Source ID |
|---|---|---|---|
| 1 | Some Source | url | {src} |

### Flagship season — audio
| Ep | Title | Format | Len | Status | Artifact ID |
|----|-------|--------|-----|--------|-------------|
| 1 | Ep 1 — Intro | deep_dive | default | done | {a1} |
| 2 | Ep 2 — Next | deep_dive | long | done | {a2} |
| 3 | Ep 3 — Three | deep_dive | default | done | {a3} |
| 4 | Ep 4 — Four | deep_dive | default | done | {a4} |

### Study aids
| Ep | Topic | Study Guide ID | Quiz ID |
|----|-------|----------------|---------|
| 1 | intro | {g1} | {q1} |
""",
        artifact_map=f"""{{
  "notebook_id": "{nb1}",
  "audio": {{ "1": {{"id":"{a1}","title":"Ep 1 — Intro"}}, "2": {{"id":"{a2}","title":"Ep 2 — Next"}} }},
  "quizzes": {{ "1": {{"id":"{q1}","title":"Ep 1 — Quiz"}} }},
  "study_guides": {{ "1": {{"id":"{g1}","title":"Ep 1 — Study Guide"}} }}
}}""",
    )

    # 2) Sparse interview-prep, NO map, reordered + short rows, truncated ids.
    nb2 = uid("nbtwo")
    write_notebook(
        root,
        "acme-interview-prep",
        f"""---
notebook_id: {nb2}
template: interview-prep
title: Acme Interview Prep
---

## Artifacts
| Type | Title | Artifact ID | Local file |
|---|---|---|---|
| Report — Anticipated Questions | Acme Prep | 1a2b3c4d | reports/x.md |
| Flashcards | Acme Cards | 5e6f7a8b | cards.md |

### Screen Ready Season
| Ep | Title | Artifact ID |
|---|---|---|
| S1E1 | The Briefing | 9c8d7e6f |
| S1E2 | Know the Firm | 0011aabb |
| (broken row with no id) |
""",
    )

    # 3) Archived/merged notebook (status: archived) — still renders.
    nb3 = uid("nbthree")
    write_notebook(
        root,
        "old-archived",
        f"""---
notebook_id: {nb3}
title: Old Archived
template: learning-topic
status: archived
merged_into: alpha-learning
tags: [learning, archived]
---

# Old Archived
| Type | Format | Status | ID |
|---|---|---|---|
| Quiz | medium | done | {uid("oldquiz")} |
""",
    )

    # 4) Malformed YAML frontmatter + notebook_id recoverable only from the URL in the body.
    nb4 = uid("nbfour")
    write_notebook(
        root,
        "broken-fm",
        f"""---
title: Broken Frontmatter
tags: [this is : not : valid yaml
template learning-topic
---

# Broken FM
See https://notebooklm.google.com/notebook/{nb4} for the notebook.

| Type | Title | Status | ID |
|---|---|---|---|
| Audio | A Lonely Episode | done | {uid("lonelyaud")} |
""",
    )

    # 5) Truly unusable: no notebook_id anywhere -> skipped (not a crash).
    write_notebook(
        root,
        "no-id",
        """---
title: No Id Notebook
---
# No Id
Nothing linkable here.
""",
    )

    # 6) Empty-ish README (no frontmatter, no tables).
    write_notebook(root, "empty", "# Just a title and nothing else\n")

    # A non-notebook dir (no README) should be ignored.
    (root / "not-a-notebook").mkdir()
    # A dotfile dir should be ignored.
    (root / ".obsidian").mkdir()

    return root
