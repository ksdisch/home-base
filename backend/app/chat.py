"""Chat with the brief (M5): one grounded follow-up answer per served brief item.

``POST /api/brief/chat`` runs a single non-interactive ``claude -p`` on Kyle's Claude
subscription. Two lane guards, inherited from the sweep pipeline (M3): the child env has
``ANTHROPIC_API_KEY`` scrubbed so a stray exported key can never silently flip a question
onto metered API billing, and **no tools are whitelisted** — ``-p`` auto-denies the rest —
so the answer is grounded in the served item plus model knowledge, and the prompt says so
honestly instead of pretending at freshness. Every exchange (including failures) appends a
usage row to ``<data_dir>/brief-chat.jsonl`` — backend data, because the backend stays
strictly read-only over ``data/sweeps``.

The test seam mirrors :class:`app.nlm.client.NlmClient`: inject a ``runner`` (and override
``deps.get_brief_chat_client``) so tests never touch a real ``claude``.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from .config import get_settings

_MAX_QUESTION_CHARS = 2000
_TIMEOUT_SECONDS = 120.0


class BriefChatError(Exception):
    """The chat run failed (CLI missing, timeout, error envelope, unparseable output)."""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


@dataclass
class ChatResult:
    args: list[str]
    stdout: str
    stderr: str
    returncode: int


Runner = Callable[[Sequence[str]], ChatResult]


def _scrubbed_env() -> Dict[str, str]:
    """The child env for ``claude -p``: never let an exported API key switch the lane."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def build_prompt(topic: Dict[str, Any], item: Dict[str, Any], question: str, brief_date: str) -> str:
    """One self-contained prompt: honesty rules, the served item verbatim, the question."""
    try:
        d = date.fromisoformat(brief_date)
        day_human = f"{d:%A}, {d:%B} {d.day}, {d.year}"
    except ValueError:
        day_human = brief_date
    sources = "; ".join(
        f"{s.get('title', '')} — {s.get('url', '')}" for s in item.get("sources", [])
    )
    return (
        "You are the follow-up assistant inside Kyle's private morning-brief app. Below is "
        f"one item from the brief he is reading (topic: {topic.get('title', topic.get('slug', ''))}, "
        f"brief date: {day_human}, as of {topic.get('as_of') or 'unknown'}), then his "
        "question about it.\n\n"
        "Answer the question directly and concisely — a short paragraph or two, plain "
        "Markdown allowed. You have NO web or tool access in this session: ground your "
        "answer in the item below plus your general knowledge, be explicit about "
        "uncertainty, and if the question really needs information fresher than this brief, "
        "say that plainly instead of guessing.\n\n"
        "ITEM\n"
        f"Headline: {item.get('headline', '')}\n"
        f"Attribution: {item.get('attribution') or '—'}\n"
        f"Digest: {item.get('digest') or '—'}\n"
        f"Why it matters: {item.get('why_it_matters') or '—'}\n"
        f"Sources: {sources or '—'}\n\n"
        "QUESTION\n"
        f"{question}"
    )


class BriefChatClient:
    def __init__(
        self,
        binary: Optional[str] = None,
        model: Optional[str] = None,
        *,
        runner: Optional[Runner] = None,
    ) -> None:
        settings = get_settings()
        self.binary = binary or settings.claude_bin
        self.model = model or settings.brief_chat_model
        self._runner = runner  # injected in tests; default uses subprocess

    def ask(self, prompt: str, *, timeout: float = _TIMEOUT_SECONDS) -> Dict[str, Any]:
        """Run one headless exchange; return ``{"answer": str, "envelope": dict}``.

        The ``--output-format json`` envelope carries the answer in ``.result`` plus the
        cost/usage fields the ledger records (the same shape sweeps/envelope.py unwraps).
        """
        args = ["-p", prompt, "--model", self.model, "--output-format", "json"]
        if self._runner is not None:
            res = self._runner(args)
        else:
            try:
                proc = subprocess.run(
                    [self.binary, *args],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=_scrubbed_env(),
                    stdin=subprocess.DEVNULL,  # never stall on stdin (the M3 lesson)
                )
            except FileNotFoundError as e:
                raise BriefChatError(
                    "claude CLI not found — is it on the backend's PATH?", detail=str(e)
                ) from e
            except subprocess.TimeoutExpired as e:
                raise BriefChatError(
                    f"chat timed out after {int(timeout)}s", detail=str(e)
                ) from e
            res = ChatResult(list(args), proc.stdout, proc.stderr, proc.returncode)

        if res.returncode != 0:
            raise BriefChatError(
                "claude exited with an error",
                detail=(res.stderr or res.stdout).strip()[:500],
            )
        try:
            envelope = json.loads(res.stdout)
        except json.JSONDecodeError as e:
            raise BriefChatError(
                "claude returned no parseable result envelope", detail=res.stdout[:200]
            ) from e
        if not isinstance(envelope, dict) or envelope.get("is_error"):
            raise BriefChatError(
                "claude reported an error result",
                detail=str(envelope.get("result", ""))[:500] if isinstance(envelope, dict) else "",
            )
        answer = envelope.get("result")
        if not isinstance(answer, str) or not answer.strip():
            raise BriefChatError("claude returned an empty answer")
        return {"answer": answer.strip(), "envelope": envelope}


def append_chat_ledger(
    path: Path,
    *,
    brief_date: str,
    topic_slug: str,
    item_id: str,
    model: str,
    envelope: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Best-effort usage row (errors included) — observability must never eat an answer."""
    env = envelope or {}
    usage = env.get("usage") or {}
    row = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brief_date": brief_date,
        "topic": topic_slug,
        "item_id": item_id,
        "model": model,
        "is_error": error is not None,
        "total_cost_usd": env.get("total_cost_usd"),
        "duration_ms": env.get("duration_ms"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }
    if error:
        row["error"] = error[:300]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def max_question_chars() -> int:
    return _MAX_QUESTION_CHARS
