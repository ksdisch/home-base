# Overnight Chief of Staff — the brief you approve, not read

**Status:** Idea — not committed. Added by `/brainstorm` (Moonshot mode) on 2026-07-19.

_A nightly agent runs after the 06:00 sweep, drafts the morning's real errands (stale follow-up emails, job-tracker reconciliation, a Louis med refill, the finance snapshot) as proposed actions, and the Today page opens as an after-action log of what it did — each action one-tap approve, edit, or undo._

## Premise

Home Base already owns two act-capable primitives — M5's scrubbed-key headless `claude -p` lane and M3's launchd scheduler — that do nothing between sweeps. Overnight, a new pass wakes them to draft the real errands of Kyle's morning as reversible proposals, and the Today page inverts from 'here's what happened in the world' to 'here are the six things I handled; approve, edit, or undo.' The approve/undo queue is deliberately made the product's front door because it is simultaneously the feature and the safety gate on the largest acting surface the project has ever added.

**Why now:** M5 shipped the headless `claude -p` subscription lane and M3 the launchd 06:00 scheduler — both act-capable primitives now sit idle every night. The ~08-03 v1 check measures whether significant events 'reach Kyle HERE first'; the strongest possible way to win that criterion is for the brief to have already acted on those events before he wakes, not merely surfaced them.

## The bet

That Kyle will trust Home Base enough to let it MOVE on his behalf, not just report accurately — a categorically higher bar than the current trust promise. This targets assumption 4 (no new LLM surface without a gate) head-on: it is by far the largest generative-AND-acting surface the project has ever proposed, and the audacious answer to 'how do you gate acting' is that the approve/undo queue IS the gate, promoted to the product's front door. A veteran flinches because a zero-fabrication, no-tools-in-chat product is now proposing to draft on Kyle's real accounts overnight — the exact surface every prior milestone deliberately refused to add.

## Decisions / open questions

1) The flagship errands (draft-follow-up, gmail-triage, app-sync, finance-review) live in Kyle's vault/Cowork ecosystem, NOT this repo — does v0 shell out to those local skills, or start with a smaller in-repo-only set of proposals, keeping the identity flip while the external bridge matures? 2) Draft-only forever, or does a later gate (M0-style graded week) unlock genuine send/execute? 3) Where does an 'undo' actually reverse an action that already touched an external account — is undo real, or only 'don't send'?

## Credible first step

Add a nightly pass (new `sweeps/actions_queue.py`) wired to run after the existing sweep via the `sweeps/schedule/` launchd pattern (`com.homebase.sweep.plist.template` + `run-scheduled.sh`), reusing `backend/app/chat.py`'s scrubbed-key/no-tools headless lane to generate DRAFT-ONLY proposed actions into a new `backend/data/overnight.jsonl`; surface them as an 'Overnight' approve/undo strip pinned above the topics in `frontend/src/pages/Brief.tsx`, using the existing `create_brief_note` write path in `backend/app/api/brief.py` as the save/dismiss model. (Correction to the input wedge: the scheduler lives in `sweeps/schedule/`, not bare `sweeps/`.)

## Dependencies

backend/app/chat.py (M5 headless lane), sweeps/schedule/ launchd machinery (M3), create_brief_note write API + BriefResponse in backend/app/api/brief.py, Brief.tsx for the Overnight strip; a NEW backend/data/overnight.jsonl. External and NOT owned by this repo: the vault act-skills (draft-follow-up, gmail-triage, app-sync, finance-review) that supply the flagship errands.

## Explicitly out of scope (revisit later)

v0 sends/executes nothing — every action is a draft-only proposal in overnight.jsonl. No real email sent, no tracker mutation, no calendar write; 'undo' in v0 means 'discard the draft,' not reversing an external side effect. No auto-approve, no unattended execution without Kyle's tap.

## Identity/positioning note

identity-shift: Home Base stops being something Kyle reads and becomes an actor that reports its own overnight work — the core verb flips from brief-the-world to act-then-report, and the morning surface's front door changes from a news summary to an after-action queue.
