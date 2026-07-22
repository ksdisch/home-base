"""Compose a learning path over a topic's REAL artifacts via the M5 guarded ``claude -p`` lane (M8).

The on-demand Designer (design decision 9) reads a NotebookLM topic's real artifacts (audio / study
guides / quizzes / flashcards) and asks claude to ARRANGE them into an ordered path plus light
connective glue — an intro, per-step focus notes, one ✨ bridge-check where the topic lacks a study
guide, a closing reflection. It reuses ``app.chat.BriefChatClient`` (the subscription lane: API key
scrubbed, no web tools, scratch cwd) exactly like the bridge grader, and enforces the M0
no-fabrication bar: EVERY artifact-backed step must cite a real artifact id of the matching type, or
the whole composition is rejected and nothing is written. Never raises to the caller — a claude
hiccup, unparseable output, or a validation failure all come back as ``ok=False`` so the endpoint
never 500s (the grader posture)."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, List, Sequence

from ..chat import BriefChatClient, BriefChatError
from .manifest import PathError, validate_path_obj

_TIMEOUT_SECONDS = 240.0  # headroom; the per-kind cap below keeps even the richest topics fast

# Each artifact-backed path step kind ↔ the sidecar artifact ``type`` that may back it (the M0
# cross-check). Glue kinds (intro/bridge/reflect/recap) reference no artifact, so aren't here.
_TYPE_FOR_KIND = {"audio": "audio", "read": "study_guide", "quiz": "quiz", "flashcards": "flashcards"}

# For the prompt: the artifact types a step may reference, in learn-order, with their display label
# and the path-step kind they map to. Anything else in the catalog (video, mind_map, report…) is
# omitted — the designer can only arrange these four kinds.
_PRESENT_ORDER = (
    ("audio", "🎧 audio", "audio"),
    ("study_guide", "📖 study guides", "read"),
    ("flashcards", "🃏 flashcards", "flashcards"),
    ("quiz", "❓ quizzes", "quiz"),
)

# Cap the artifacts of each kind the designer SEES (design polish 2026-07-22). The richest topics
# (e.g. 26 audio · 11 quizzes) otherwise get arranged wholesale into a ~50-step path that blows the
# claude-lane timeout; showing a bounded, foundational-first slice keeps every generation focused +
# fast. Validation still runs against the FULL artifact set, so the M0 no-fabrication bar is intact.
_MAX_PER_KIND = {"audio": 8, "study_guide": 4, "flashcards": 3, "quiz": 3}


def _strip_fence(text: str) -> str:
    """Drop a ```json … ``` (or bare ``` … ```) wrapper if the model added one, so ``json.loads``
    sees the object. Mirrors ``app.courses.regen._strip_fence``."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\n", "", t)
        t = re.sub(r"\n?```$", "", t.rstrip())
    return t.strip()


def build_designer_prompt(topic_title: str, artifacts: Sequence[Dict[str, Any]]) -> str:
    """One self-contained authoring prompt: the task (arrange + glue), the EXACT real-artifact list
    (the only ids the model may use), and the strict-JSON output contract. Style precedent:
    ``chat.build_prompt`` / ``grader.build_bridge_prompt``."""
    groups: Dict[str, List[Dict[str, Any]]] = {t: [] for t, _, _ in _PRESENT_ORDER}
    for a in artifacts:
        t = a.get("type")
        if t in groups:
            groups[t].append(a)
    # Keep only a bounded, foundational-first slice of each kind so the richest topics compose a
    # FOCUSED path instead of arranging every artifact (design polish 2026-07-22).
    for t, items in groups.items():
        cap = _MAX_PER_KIND.get(t)
        if cap is not None and len(items) > cap:
            groups[t] = items[:cap]

    lines: List[str] = []
    for t, label, kind in _PRESENT_ORDER:
        lines.append(f'{label} — reference as kind "{kind}":')
        if groups[t]:
            for a in groups[t]:
                title = (a.get("title") or "").strip() or "(untitled)"
                lines.append(f'  - id {a.get("id")} · "{title}"')
        else:
            lines.append("  (none available)")
    artifact_block = "\n".join(lines)

    has_guide = bool(groups["study_guide"])
    bridge_rule = (
        'This topic HAS a study guide, so do NOT add a "bridge" step.'
        if has_guide
        else 'This topic has NO study guide, so insert EXACTLY ONE "bridge" step where a study '
        'guide would go — its "body" is a one- or two-sentence open-recall question the learner '
        "answers from memory (no artifact_id)."
    )

    return (
        "You are a learning designer inside Kyle's private study app. Compose ONE guided learning "
        f'path over his existing notebook "{topic_title}". You are ARRANGING real artifacts he '
        "already has (listed below) into a sensible order and adding light connective glue — you "
        "are NOT writing new lessons or inventing material.\n\n"
        "AVAILABLE ARTIFACTS — the ONLY ids you may reference. Copy each id EXACTLY; never invent, "
        "guess at, abbreviate, or modify an id:\n"
        f"{artifact_block}\n\n"
        "COMPOSE a FOCUSED path — pick the most useful artifacts and arrange them; you do NOT "
        "need to use every one (a tight, well-sequenced path beats an exhaustive dump). Build "
        "understanding: a short orientation, then listen, then read (if a study guide exists), "
        "then drill (flashcards), then test (quiz), then a brief reflection. Rules:\n"
        '- Every "audio"/"read"/"flashcards"/"quiz" step MUST carry an "artifact_id" copied '
        'exactly from the list above and an "artifact_type" (audio/study_guide/quiz/flashcards) '
        "that matches its kind. Use each artifact at most once, and feel free to omit any that "
        "don't earn a place; skip a kind that has none.\n"
        '- Add light glue with NO artifact_id: exactly one "intro" step first (a one-paragraph '
        '"body" orienting the learner); a one-line "focus" note on each artifact step; and one '
        'closing "reflect" step (a short "body" prompt).\n'
        f"- {bridge_rule}\n"
        '- Give every step a short URL-safe "id" ([A-Za-z0-9._-], unique across the path) and a '
        'human "title". Add "estimated_minutes" (an integer) on audio steps when you can gauge it.\n\n'
        "OUTPUT a single JSON object and NOTHING else — no prose, no markdown, no code fence — of "
        "this exact shape:\n"
        '{"title": "<a title for the path>", "topic": "<a short subject line>", '
        '"steps": [{"id": "...", "kind": "...", "title": "...", "focus": "...", "body": "...", '
        '"artifact_id": "...", "artifact_type": "...", "estimated_minutes": 0}]}\n'
        "Include only the fields a step needs (glue steps omit artifact_id/artifact_type; artifact "
        "steps omit body)."
    )


def _validate_against_catalog(
    steps: List[Dict[str, Any]], artifacts: Sequence[Dict[str, Any]]
) -> List[str]:
    """The M0 no-fabrication bar: every artifact-backed step must cite a REAL artifact id of this
    topic whose type matches the step kind. Returns human-readable errors ([] = clean)."""
    by_id = {a["id"]: a for a in artifacts if a.get("id")}
    errors: List[str] = []
    for s in steps:
        expected = _TYPE_FOR_KIND.get(s["kind"])
        if expected is None:
            continue  # a glue step (intro/bridge/reflect/recap) — no artifact to check
        aid = s.get("artifact_id")
        art = by_id.get(aid) if aid else None
        if art is None:
            errors.append(
                f"step '{s['id']}' cites artifact_id '{aid}', which is not a real artifact of this topic"
            )
        elif art.get("type") != expected:
            errors.append(
                f"step '{s['id']}' (kind '{s['kind']}') cites a '{art.get('type')}' artifact, "
                f"but kind '{s['kind']}' needs a '{expected}' one"
            )
    return errors


def compose_path(
    client: BriefChatClient,
    *,
    notebook_id: str,
    topic_title: str,
    artifacts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return ``{"ok", "raw": dict|None, "error": str|None, "errors": list[str], "envelope": dict|None}``.

    ``raw`` (only when ``ok``) is the validated, provenance-stamped path object ready for
    ``write_path_file`` — a clean canonical shape (only known step fields). Any failure — a claude
    hiccup, non-JSON output, a structural problem, or a fabricated/mismatched artifact id — comes
    back ``ok=False`` with nothing to write."""
    prompt = build_designer_prompt(topic_title, artifacts)
    try:
        res = client.ask(prompt, timeout=_TIMEOUT_SECONDS)
    except BriefChatError as e:
        return {"ok": False, "raw": None, "error": str(e), "errors": [], "envelope": None}
    envelope = res.get("envelope")

    try:
        obj = json.loads(_strip_fence(res["answer"]))
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "ok": False,
            "raw": None,
            "error": f"the designer did not return valid JSON ({e})",
            "errors": [],
            "envelope": envelope,
        }

    try:
        shaped = validate_path_obj(obj, notebook_id, source="generated path")
    except PathError as e:
        return {"ok": False, "raw": None, "error": None, "errors": [str(e)], "envelope": envelope}

    errors = _validate_against_catalog(shaped["steps"], artifacts)
    if errors:
        return {"ok": False, "raw": None, "error": None, "errors": errors, "envelope": envelope}

    raw = {
        "title": shaped["title"],
        "topic": shaped["topic"],
        "generated_at": date.today().isoformat(),
        "generator": f"claude -p designer ({client.model})",
        "steps": shaped["steps"],
    }
    return {"ok": True, "raw": raw, "error": None, "errors": [], "envelope": envelope}
