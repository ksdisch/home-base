"""build_designer_prompt curation (M8 designer polish 2026-07-22).

The designer used to hand the model EVERY artifact, so the richest topics (26 audio · 11 quizzes …)
composed a ~50-step path that blew the 180s claude-lane ceiling. It now shows a bounded,
foundational-first slice per kind (_MAX_PER_KIND) and asks for a FOCUSED path. These are
pure-function tests over the prompt text — no claude, no endpoint.
"""

from __future__ import annotations

from app.paths.designer import _MAX_PER_KIND, build_designer_prompt


def _artifacts(kind_counts):
    """A flat artifact list: kind -> how many. Ids are '<kind>-<n>' in order, titles distinct."""
    out = []
    for kind, n in kind_counts.items():
        for i in range(n):
            out.append({"id": f"{kind}-{i}", "type": kind, "title": f"{kind} {i}"})
    return out


def test_caps_each_kind_to_the_bound():
    # A topic far over every cap (shaped like engineering-abstractions).
    arts = _artifacts({"audio": 26, "study_guide": 11, "quiz": 11, "flashcards": 5})
    prompt = build_designer_prompt("Big Topic", arts)
    assert prompt.count("id audio-") == _MAX_PER_KIND["audio"]
    assert prompt.count("id study_guide-") == _MAX_PER_KIND["study_guide"]
    assert prompt.count("id quiz-") == _MAX_PER_KIND["quiz"]
    assert prompt.count("id flashcards-") == _MAX_PER_KIND["flashcards"]


def test_keeps_the_foundational_first_slice():
    arts = _artifacts({"audio": 20})
    prompt = build_designer_prompt("T", arts)
    cap = _MAX_PER_KIND["audio"]
    assert "id audio-0 ·" in prompt  # first kept
    assert f"id audio-{cap - 1} ·" in prompt  # last kept
    assert f"id audio-{cap} ·" not in prompt  # the (cap+1)th is dropped, not reordered in


def test_under_cap_shows_every_artifact():
    arts = _artifacts({"quiz": 2})  # under the quiz cap of 3
    prompt = build_designer_prompt("T", arts)
    assert prompt.count("id quiz-") == 2


def test_prompt_invites_a_focused_selection():
    prompt = build_designer_prompt("T", _artifacts({"audio": 3})).lower()
    assert "focused" in prompt
    assert "not need to use every" in prompt or "omit any" in prompt
