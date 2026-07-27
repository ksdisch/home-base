# The Correspondence — a second node on the wire, the anti-social-network

**Status:** Idea — not committed. Added by `/replenish` (Moonshot lane) on 2026-07-26.

_IDENTITY-SHIFT. Home Base grows a peer: one trusted human — partner, sibling, close friend — runs their own node, and each morning the two nodes exchange a tiny signed 'dispatch': up to 3 items the sender explicitly flagged 'send to peer' with their own note attached, rendered as a Dispatches strip on Today. It is the only content in Home Base chosen neither by an algorithm nor by Kyle, but by a trusted human's hand. Peer-to-peer over the same private tailnet — no cloud deploy, no auth beyond the wire, consent-based (dispatches are explicit sends, never a synced feed). The five-year shape is a quiet protocol where personal news nodes exchange human-curated items with provenance and the sender's voice attached, replacing the follower feed with a private editorial wire between people who actually trust each other._

## Premise

Kyle's morning gains a strip that no algorithm and no sweep produced: a handful of items a trusted human deliberately sent him, in their voice, with their reason attached. It is the one place in the product where the content is chosen by love and trust rather than by ranking — and it scales to a quiet network without ever becoming a feed.

**Why now:** M6 already proved the private wire — real-iPhone Tailscale reach is verified — so a second node on the same tailnet is a believable multi-year step, not a cloud project. And the anti-social-network thesis only matters while feeds still dominate; the window to build the alternative is open now.

## The bet

THE ONE THING THAT MUST BE TRUE: the durable answer to algorithmic feeds is not a better algorithm but a trusted human's hand — a small number of people you actually trust curating for each other beats any ranker, and a private signed wire between owned nodes is the shape that delivers it without becoming a social network. TARGETS assumption 5 (single-user) — deliberately breaks 'single-user' while keeping every other clause: local-first, tailnet-only, consent-based, no cloud. VETERAN FLINCH: this violates the project's most-restated axiom (one user, restated across M6 and the whole memory) and hands another person editorial access to Kyle's morning trust surface — dispatches bypass the M0 sourcing bar, so they must wear untrusted-item-style framing. A veteran will say 'we said single-user a dozen times'; the point is that the axiom was a scope choice, not a law.

## Decisions / open questions

(1) Who is the real first peer, and do they run a full Home Base node or a thin dispatch-only client? (2) Signing/identity scheme on the tailnet (tailscale identity headers vs a shared key)? (3) Do dispatches wear untrusted-item framing permanently, or earn trust like agents in the Agent Gate?

## Credible first step

Loopback proof on one Mac, no second human required (believable for the horizon): a 'send to peer' card action writing backend/data/dispatch-outbox.jsonl, a GET /api/dispatch/outbox serving a signed JSON digest (item, sources, sender note, sender id), and an importer that renders an inbox strip on Today. Boot a second backend instance on another port as the fake peer and verify the round trip end-to-end. The durable artifact is the dispatch schema itself — define it before any real peer exists, mirroring how the codebase defines seams (CalendarPort, the chat Runner) before the real adapter.

## Dependencies

Tailscale reach (proven in M6), a dispatch schema (the durable artifact), new outbox/inbox endpoints + a Today strip; deliberately none on the sweep pipeline.

## Explicitly out of scope (revisit later)

Never a feed, never a follower model, never cloud-relayed; no auto-sync — every dispatch is an explicit human send. Single peer in v1; the "quiet protocol" network is the 5-year shape, not the build.

## Identity/positioning note

identity-shift: breaks the single-user axiom and adds the product's first outbound-to-a-human surface. What changes about what-this-project-IS: Home Base stops being a solipsistic single-user brief and becomes one node in a private trust network — a personal news wire, not a personal news app.
