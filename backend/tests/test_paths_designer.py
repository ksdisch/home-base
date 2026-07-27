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


# -- video is never part of the audio spine (bug #3) -------------------------------------
# _PRESENT_ORDER omits video by construction (design decision 12: video is supplementary,
# audio is the backbone). That guarantee is only as good as the catalog's typing — a video
# row typed 'audio' walks straight into the 🎧 group and the M0 cross-check waves it
# through, since the step's kind and the artifact's (wrong) type agree.


def test_video_artifacts_never_enter_the_audio_group():
    arts = [
        {"id": "aud-1", "type": "audio", "title": "Ep 1 — Deep dive"},
        {"id": "vid-1", "type": "video", "title": "Ep 1 — Whiteboard walkthrough"},
    ]
    prompt = build_designer_prompt("Jacobians", arts)
    audio_block = prompt.split("🎧 audio")[1].split("📖 study guides")[0]
    assert "id aud-1" in audio_block
    assert "vid-1" not in prompt  # not in the audio group, and not anywhere else


def test_a_video_only_topic_offers_no_audio_at_all():
    """The honest degrade: with video mistyped as audio this topic looked like it had a
    listen spine; correctly typed, the designer is told there is none."""
    arts = [{"id": f"vid-{i}", "type": "video", "title": f"Ep {i} — Whiteboard"} for i in range(4)]
    prompt = build_designer_prompt("Jacobians", arts)
    audio_block = prompt.split("🎧 audio")[1].split("📖 study guides")[0]
    assert "(none available)" in audio_block
    assert "vid-" not in prompt


def test_catalog_typing_feeds_the_designer_video_free(tmp_path):
    """End to end over the real parser: a jlens-shaped whiteboard series must not become
    the audio spine of a generated path."""
    from app.catalog.markdown_tables import classify_table_artifacts, extract_tables

    md = (
        "## Audio series\n"
        "| Ep | Title | Artifact ID |\n|---|---|---|\n"
        "| 1 | Ep 1 — The gradient | aaaaaaaa-1111-1111-1111-111111111111 |\n"
        "\n## Video series (whiteboard)\n"
        "| Ep | Title | Artifact ID |\n|---|---|---|\n"
        "| 1 | Ep 1 — What a Jacobian Is | bbbbbbbb-2222-2222-2222-222222222222 |\n"
    )
    raw = [a for t in extract_tables(md) for a in classify_table_artifacts(t)]
    arts = [{"id": a.artifact_id, "type": a.type, "title": a.title} for a in raw]

    prompt = build_designer_prompt("Jacobians", arts)
    assert "aaaaaaaa-1111-1111-1111-111111111111" in prompt
    assert "bbbbbbbb-2222-2222-2222-222222222222" not in prompt
