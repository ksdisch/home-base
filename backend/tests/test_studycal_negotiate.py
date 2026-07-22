"""app.studycal.negotiate — the grounded claude -p negotiation lane (v0).

Kyle's call (2026-07-22): add a conversational lane on top of the deterministic planner. Crucially it
only ever turns a free-text preference into PLANNER KNOBS (evening window, session length, how many
blocks) + a one-line message — it never emits specific times, so all slot selection stays
deterministic and grounded (the M0 no-fabrication bar). A claude hiccup degrades to the base config,
never a 500.
"""

from __future__ import annotations

import json

from app.chat import BriefChatClient, ChatResult
from app.studycal.negotiate import build_negotiate_prompt, negotiate_plan
from app.studycal.planner import PlanConfig


def _runner(answer_text: str, *, code: int = 0):
    """A fake claude runner: wraps ``answer_text`` as the model's ``.result`` in a JSON envelope."""

    def run(args):
        envelope = json.dumps(
            {
                "result": answer_text,
                "total_cost_usd": 0.001,
                "duration_ms": 12,
                "usage": {"input_tokens": 20, "output_tokens": 10},
            }
        )
        return ChatResult(list(args), envelope, "", code)

    return run


def _client(answer_text: str, *, code: int = 0) -> BriefChatClient:
    return BriefChatClient(model="sonnet", runner=_runner(answer_text, code=code))


BASE = PlanConfig()


def test_preference_maps_to_clamped_planner_knobs() -> None:
    answer = json.dumps(
        {
            "day_start_hour": 7,
            "day_end_hour": 9,
            "session_minutes": 30,
            "message": "Mornings it is — 7-9am, 30-minute sessions.",
        }
    )
    out = negotiate_plan(_client(answer), preference="mornings only, short sessions", base_config=BASE)
    assert out["ok"] is True
    assert out["config"].day_start_hour == 7
    assert out["config"].day_end_hour == 9
    assert out["config"].session_minutes == 30
    assert "Mornings" in out["message"]


def test_extreme_or_nonnumeric_knobs_are_clamped_or_ignored() -> None:
    answer = json.dumps({"session_minutes": 999, "day_start_hour": 5, "max_blocks": "lots"})
    out = negotiate_plan(_client(answer), preference="cram everything", base_config=BASE)
    assert out["config"].session_minutes == 180  # clamped to the ceiling
    assert out["config"].day_start_hour == 5  # in range → kept
    assert out["config"].max_blocks == BASE.max_blocks  # non-numeric ignored, base kept


def test_unparseable_model_output_degrades_to_the_base_config() -> None:
    out = negotiate_plan(_client("sure, mornings sound great!"), preference="x", base_config=BASE)
    assert out["ok"] is True  # the call ran; we just couldn't extract knobs
    assert out["config"] == BASE


def test_a_claude_hiccup_degrades_without_raising() -> None:
    out = negotiate_plan(_client("boom", code=1), preference="x", base_config=BASE)
    assert out["ok"] is False
    assert out["config"] == BASE
    assert out["error"]


def test_prompt_carries_the_preference_and_forbids_inventing_times() -> None:
    prompt = build_negotiate_prompt("prefer Tuesday and Thursday evenings", BASE)
    assert "prefer Tuesday and Thursday evenings" in prompt
    low = prompt.lower()
    assert "time" in low and ("do not" in low or "never" in low)  # explicit no-invented-times rule
