import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BriefShell } from "../components/BriefShell";
import Brief from "./Brief";

// Mock the API client so the page renders deterministically without a backend. The Today
// page also mounts the Your-learning strip (review + courses) and the note composer, so
// those calls need deterministic defaults too.
const briefWithMeta = vi.fn();
const logBriefVisit = vi.fn();
const review = vi.fn();
const courses = vi.fn();
const briefHabit = vi.fn();
const addBriefNote = vi.fn();
const deleteBriefNote = vi.fn();
const sweepBrief = vi.fn();
const approveOvernight = vi.fn();
const discardOvernight = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    briefWithMeta: () => briefWithMeta(),
    logBriefVisit: () => logBriefVisit(),
    review: () => review(),
    courses: () => courses(),
    briefHabit: () => briefHabit(),
    briefRunsSummary: () => Promise.resolve({ generated_at: "now", latest: null, days: [], window_days: 7, cost_usd: 0, errors: 0, missing_days: 0 }),
    addBriefNote: (body: unknown) => addBriefNote(body),
    deleteBriefNote: (id: number) => deleteBriefNote(id),
    briefAudioUrl: () => "/api/brief/audio",
    sweepBrief: () => sweepBrief(),
    approveOvernight: (id: string) => approveOvernight(id),
    discardOvernight: (id: string) => discardOvernight(id),
  },
}));

// The page loads via briefWithMeta (M6): the payload plus whether the service worker
// replayed it from the offline cache.
const online = (b: unknown) => ({ brief: b, fromCache: false });
const offline = (b: unknown) => ({ brief: b, fromCache: true });

beforeEach(() => {
  briefWithMeta.mockReset();
  logBriefVisit.mockReset();
  review.mockReset();
  courses.mockReset();
  briefHabit.mockReset();
  addBriefNote.mockReset();
  deleteBriefNote.mockReset();
  sweepBrief.mockReset();
  approveOvernight.mockReset();
  discardOvernight.mockReset();
  logBriefVisit.mockResolvedValue({ ok: true, day: "2026-07-14", visited_at: "" });
  // Quiet defaults: nothing due, no courses, no habit signal → the strips hide themselves.
  review.mockResolvedValue({ generated_at: "now", has_data: false, due_count: 0, items: [] });
  courses.mockResolvedValue({ generated_at: "now", courses: [] });
  briefHabit.mockResolvedValue({ generated_at: "now", weeks: [] });
});

const ITEM = {
  id: "abc123def456",
  headline: "OpenAI lifts caps",
  attribution: "Bleeping Computer, July 13, 2026",
  digest: "OpenAI removed the rolling cap.",
  why_it_matters: "Session budgets change.",
  sources: [{ title: "Bleeping Computer", url: "https://example.com/a" }],
  notes: [] as unknown[],
};

const STRUCTURED = {
  generated_at: "now",
  has_data: true,
  date: "2099-01-01", // far future so the stale banner can't flake on real dates
  topics: [
    {
      slug: "ai-llms",
      title: "AI / LLMs",
      as_of: "2099-01-01 07:05 CDT",
      top_line: "One release actually worth your time.",
      context_note: "Dead-quiet window.",
      items: [ITEM],
      raw_markdown: null,
      error: null,
    },
  ],
};

// FR15: the page consumes BriefShell (payload + persistent audio live above the
// routes), so the harness mounts the real shell around it — same api mock, same DOM.
function renderBrief() {
  return render(
    <MemoryRouter>
      <BriefShell>
        <Brief />
      </BriefShell>
    </MemoryRouter>,
  );
}

describe("Brief (Today page)", () => {
  it("renders a structured topic — items, sources, as-of — and logs a visit", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("AI / LLMs")).toBeInTheDocument();
    expect(screen.getByText(/as of 2099-01-01 07:05 CDT/)).toBeInTheDocument();
    expect(screen.getByText("One release actually worth your time.")).toBeInTheDocument();
    expect(screen.getByText("Dead-quiet window.")).toBeInTheDocument();
    expect(screen.getByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByText(/Why it matters:/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bleeping Computer" })).toHaveAttribute(
      "href",
      "https://example.com/a",
    );
    expect(logBriefVisit).toHaveBeenCalled();
  });

  it("cascades the sections in on a cold load (⑥)", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    await screen.findByText("AI / LLMs");
    // On a genuine cold load each section is wrapped in the motion-safe cascade class; the
    // CSS animation itself lives only under prefers-reduced-motion: no-preference, so
    // reduced-motion users get the instant paint.
    const wrapper = screen.getByText("AI / LLMs").closest("section")?.parentElement;
    expect(wrapper?.className).toContain("brief-cascade");
  });

  it("renders a raw-markdown fallback topic (legacy md-only day) with a stale hint", async () => {
    briefWithMeta.mockResolvedValue(
      online({
      generated_at: "now",
      has_data: true,
      date: "2026-07-13", // in the past by the time this runs → stale banner
      topics: [
        {
          slug: "fantasy-football",
          title: "Fantasy football",
          as_of: "2026-07-13 16:47 CDT",
          top_line: null,
          context_note: null,
          items: [],
          raw_markdown: "**Quiet camp-eve Monday.**\n\n### An item — PFR, July 11\nBody text.",
            error: null,
          },
        ],
      }),
    );
    renderBrief();

    expect(await screen.findByText("Fantasy football")).toBeInTheDocument();
    expect(screen.getByText("Quiet camp-eve Monday.")).toBeInTheDocument();
    expect(screen.getByText(/An item — PFR, July 11/)).toBeInTheDocument();
  });

  it("empty state points at make sweep", async () => {
    briefWithMeta.mockResolvedValue(
      online({ generated_at: "now", has_data: false, date: null, topics: [] }),
    );
    renderBrief();

    expect(await screen.findByText(/No sweeps yet/)).toBeInTheDocument();
    expect(screen.getByText("make sweep")).toBeInTheDocument();
  });

  it("a failed brief load still shows the error banner (and never a blank page)", async () => {
    briefWithMeta.mockRejectedValue(new Error("backend down"));
    renderBrief();

    expect(await screen.findByText(/Couldn't load the brief/)).toBeInTheDocument();
    expect(screen.getByText(/backend down/)).toBeInTheDocument();
  });

  it("renders an item's existing notes and saves a new one from the composer", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        topics: [
        {
          ...STRUCTURED.topics[0],
          items: [
            {
              ...ITEM,
              notes: [
                {
                  id: 1,
                  item_id: ITEM.id,
                  topic_slug: "ai-llms",
                  topic_title: "AI / LLMs",
                  brief_date: "2099-01-01",
                  item_headline: ITEM.headline,
                  body: "An earlier take.",
                  created_at: "t1",
                },
              ],
            },
          ],
        },
        ],
      }),
    );
    addBriefNote.mockResolvedValue({
      id: 2,
      item_id: ITEM.id,
      topic_slug: "ai-llms",
      topic_title: "AI / LLMs",
      brief_date: "2099-01-01",
      item_headline: ITEM.headline,
      body: "My hot take",
      created_at: "t2",
    });
    renderBrief();

    expect(await screen.findByText("An earlier take.")).toBeInTheDocument();

    fireEvent.click(screen.getByText("+ Add note"));
    fireEvent.change(screen.getByPlaceholderText(/Your take or question/), {
      target: { value: "My hot take" },
    });
    fireEvent.click(screen.getByText("Save note"));

    await waitFor(() => expect(screen.getByText("My hot take")).toBeInTheDocument());
    expect(addBriefNote).toHaveBeenCalledWith(
      expect.objectContaining({
        item_id: "abc123def456",
        topic_slug: "ai-llms",
        brief_date: "2099-01-01",
        item_headline: "OpenAI lifts caps",
        body: "My hot take",
      }),
    );
  });

  it("surfaces due reviews and active courses in the Your-learning strip", async () => {
    briefWithMeta.mockResolvedValue(
      online({ generated_at: "now", has_data: false, date: null, topics: [] }),
    );
    review.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      due_count: 1,
      items: [
        {
          notebook_id: "nb1",
          title: "SQL Joins",
          due: true,
          reason: "3 shaky questions",
          mastery: 0.4,
          decayed: 0.2,
          priority: 1,
          total_misses: 3,
          shaky_questions: 3,
        },
        {
          notebook_id: "nb2",
          title: "Fresh topic",
          due: false,
          reason: "",
          mastery: 0.9,
          decayed: 0.9,
          priority: 0,
          total_misses: 0,
          shaky_questions: 0,
        },
      ],
    });
    courses.mockResolvedValue({
      generated_at: "now",
      courses: [{ slug: "sql-101", title: "SQL 101", progress_pct: 40 }],
    });
    renderBrief();

    expect(await screen.findByText("Your learning")).toBeInTheDocument();
    expect(screen.getByText("SQL Joins")).toBeInTheDocument();
    expect(screen.queryByText("Fresh topic")).not.toBeInTheDocument(); // only DUE items surface
    expect(screen.getByText("SQL 101")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start a session/ })).toHaveAttribute(
      "href",
      "/plan",
    );
  });

  it("offline replay shows the honest banner (and suppresses the make-sweep stale hint)", async () => {
    // A past date would normally trigger the stale banner — offline wins instead,
    // because `make sweep` is impossible when the hub is unreachable.
    briefWithMeta.mockResolvedValue(offline({ ...STRUCTURED, date: "2026-07-01" }));
    renderBrief();

    expect(await screen.findByText("Offline copy")).toBeInTheDocument();
    expect(screen.getByText(/cached last brief/)).toBeInTheDocument();
    expect(screen.queryByText(/This brief is from a previous day/)).not.toBeInTheDocument();
  });

  it("offline replay disables the note + Ask composers (writes never queue)", async () => {
    briefWithMeta.mockResolvedValue(offline(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add note" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Ask about this" })).toBeDisabled();
  });

  it("offline replay disables the per-note delete too — the ✕ escaped the M6 pass (#16)", async () => {
    briefWithMeta.mockResolvedValue(
      offline({
        ...STRUCTURED,
        topics: [
          {
            ...STRUCTURED.topics[0],
            items: [
              {
                ...ITEM,
                notes: [
                  {
                    id: 7,
                    item_id: ITEM.id,
                    topic_slug: "ai-llms",
                    topic_title: "AI / LLMs",
                    brief_date: "2099-01-01",
                    item_headline: ITEM.headline,
                    body: "An earlier take.",
                    created_at: "t1",
                  },
                ],
              },
            ],
          },
        ],
      }),
    );
    renderBrief();

    expect(await screen.findByText("An earlier take.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete note 7" })).toBeDisabled();
  });

  it("inline note delete holds behind an undo toast — Undo never calls the API (FR10)", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        topics: [
          {
            ...STRUCTURED.topics[0],
            items: [
              {
                ...ITEM,
                notes: [
                  {
                    id: 7,
                    item_id: ITEM.id,
                    topic_slug: "ai-llms",
                    topic_title: "AI / LLMs",
                    brief_date: "2099-01-01",
                    item_headline: ITEM.headline,
                    body: "An earlier take.",
                    created_at: "t1",
                  },
                ],
              },
            ],
          },
        ],
      }),
    );
    deleteBriefNote.mockResolvedValue({ ok: true });
    renderBrief();
    await screen.findByText("An earlier take.");

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByRole("button", { name: "Delete note 7" }));
      expect(screen.queryByText("An earlier take.")).not.toBeInTheDocument(); // vanishes now
      fireEvent.click(screen.getByRole("button", { name: "Undo" }));
      expect(screen.getByText("An earlier take.")).toBeInTheDocument(); // caught it
      act(() => {
        vi.runAllTimers();
      });
      expect(deleteBriefNote).not.toHaveBeenCalled(); // no API mutation at all
    } finally {
      vi.useRealTimers();
    }
  });

  it("a failing audio load hides the player instead of leaving a broken one (#15)", async () => {
    // The cached brief says audio_available, but offline the mp3 may be uncached (iOS
    // Range probes → 206 → never stored) or evicted — the promise is 'no player, no
    // broken promise', so a media error removes the player.
    briefWithMeta.mockResolvedValue(offline({ ...STRUCTURED, audio_available: true }));
    renderBrief();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const player = document.querySelector("audio");
    expect(player).not.toBeNull();
    fireEvent.error(player!);
    await waitFor(() => expect(document.querySelector("audio")).toBeNull());
    expect(screen.queryByText(/Listen to this brief/)).not.toBeInTheDocument();
  });

  it("online, the composers stay enabled", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add note" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Ask about this" })).toBeEnabled();
  });

  // QU12: a topic that didn't run is named on the page, never just absent.

  it("names the active topics that didn't run in a banner", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        missing_topics: [
          { slug: "fantasy-football", title: "Fantasy football" },
          { slug: "st-louis-blues", title: "St. Louis Blues" },
        ],
      }),
    );
    renderBrief();

    expect(await screen.findByText(/2 topics didn't run today/)).toBeInTheDocument();
    expect(screen.getByText(/Fantasy football · St\. Louis Blues/)).toBeInTheDocument();
    // The topic that DID run still renders normally below the banner.
    expect(screen.getByText("AI / LLMs")).toBeInTheDocument();
  });

  it("uses singular copy for one missing topic", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        missing_topics: [{ slug: "fantasy-football", title: "Fantasy football" }],
      }),
    );
    renderBrief();

    expect(await screen.findByText(/1 topic didn't run today/)).toBeInTheDocument();
  });

  it("shows no didn't-run banner when the field is empty or absent (older cached payloads)", async () => {
    // STRUCTURED deliberately has no missing_topics key — the pre-QU12 shape a stale
    // service-worker cache can replay; the page must neither crash nor invent a banner.
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("AI / LLMs")).toBeInTheDocument();
    expect(screen.queryByText(/didn't run today/)).not.toBeInTheDocument();
  });

  it("suppresses the didn't-run banner on an offline replay (the cached morning is already flagged)", async () => {
    briefWithMeta.mockResolvedValue(
      offline({
        ...STRUCTURED,
        missing_topics: [{ slug: "fantasy-football", title: "Fantasy football" }],
      }),
    );
    renderBrief();

    expect(await screen.findByText("Offline copy")).toBeInTheDocument();
    expect(screen.queryByText(/didn't run today/)).not.toBeInTheDocument();
  });

  it("shows the habit strip when there's weekly signal, dropping all-zero history weeks", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    briefHabit.mockResolvedValue({
      generated_at: "now",
      weeks: [
        { week_start: "2026-06-29", mornings: 0, notes: 0 }, // pre-habit week: kept out of history
        { week_start: "2026-07-06", mornings: 5, notes: 2 },
        { week_start: "2026-07-13", mornings: 3, notes: 4 }, // current week
      ],
    });
    renderBrief();

    expect(await screen.findByText("Habit check:")).toBeInTheDocument();
    expect(screen.getByText(/3 of 5 mornings/)).toBeInTheDocument();
    expect(screen.getByText(/4 of 3 notes/)).toBeInTheDocument();
    expect(screen.getByText(/5m \/ 2n/)).toBeInTheDocument(); // previous-weeks history line
    expect(screen.queryByText(/0m \/ 0n/)).not.toBeInTheDocument();
  });

  it("hides the habit strip when there's no signal at all", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    briefHabit.mockResolvedValue({
      generated_at: "now",
      weeks: [{ week_start: "2026-07-13", mornings: 0, notes: 0 }],
    });
    renderBrief();

    await screen.findByText("AI / LLMs"); // page settled
    expect(screen.queryByText("Habit check:")).not.toBeInTheDocument();
  });

  // PR5 sweep-trust gauge: the last accuracy re-grade rides the habit strip so an
  // ungraded stretch is visible instead of assumed fine.

  const isoDaysAgo = (n: number) => {
    const d = new Date();
    d.setDate(d.getDate() - n);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  };

  const HABIT_SIGNAL = {
    generated_at: "now",
    weeks: [{ week_start: "2026-07-13", mornings: 3, notes: 1 }],
  };

  it("shows the last accuracy-graded date on the habit strip (fresh — no re-grade nag)", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    briefHabit.mockResolvedValue({ ...HABIT_SIGNAL, last_graded: isoDaysAgo(3) });
    renderBrief();

    expect(await screen.findByText(/Sweep trust:/)).toBeInTheDocument();
    expect(screen.getByText(/last accuracy-graded/)).toBeInTheDocument();
    expect(screen.queryByText(/re-grade due/)).not.toBeInTheDocument();
  });

  it("flags a stale grade (>30 days) as re-grade due", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    briefHabit.mockResolvedValue({ ...HABIT_SIGNAL, last_graded: "2020-01-01" });
    renderBrief();

    expect(await screen.findByText(/Sweep trust:/)).toBeInTheDocument();
    expect(screen.getByText(/re-grade due/)).toBeInTheDocument();
  });

  it("says so honestly when there's no accuracy grade on record", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    briefHabit.mockResolvedValue({ ...HABIT_SIGNAL, last_graded: null });
    renderBrief();

    expect(await screen.findByText(/no accuracy grade on record/)).toBeInTheDocument();
  });

  // QU3 audio resume: a walk gets interrupted (call, locked phone, backgrounded PWA) —
  // the ~5-min cut must pick up where it left off, not snap back to 0:00. Position is
  // keyed by brief date so yesterday's spot can't bleed into today's brief.

  it("saves playback position to localStorage keyed by brief date (QU3)", async () => {
    localStorage.removeItem("audio-pos-2099-01-01");
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, audio_available: true }));
    renderBrief();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const player = document.querySelector("audio")!;
    Object.defineProperty(player, "currentTime", { value: 137, writable: true, configurable: true });
    // Bug #5: a position is only persisted once the element has said which track it
    // loaded, so the resume key can't be poisoned by the previous day's playhead. Real
    // media always fires loadedmetadata before its first timeupdate.
    fireEvent.loadedMetadata(player);
    fireEvent.timeUpdate(player);
    expect(localStorage.getItem("audio-pos-2099-01-01")).toBe("137");
  });

  it("resumes from the saved position when the audio loads (QU3)", async () => {
    localStorage.setItem("audio-pos-2099-01-01", "205.5");
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, audio_available: true }));
    renderBrief();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const player = document.querySelector("audio")!;
    Object.defineProperty(player, "currentTime", { value: 0, writable: true, configurable: true });
    fireEvent.loadedMetadata(player);
    expect(player.currentTime).toBe(205.5);
    localStorage.removeItem("audio-pos-2099-01-01");
  });

  it("clears the saved position when playback ends (QU3)", async () => {
    localStorage.setItem("audio-pos-2099-01-01", "290");
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, audio_available: true }));
    renderBrief();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    fireEvent.ended(document.querySelector("audio")!);
    expect(localStorage.getItem("audio-pos-2099-01-01")).toBeNull();
  });

  // QU4 topic chips: 8 roster topics render in fixed sweeps/topics.json order — a chip
  // row jumps straight to the one you opened the app for instead of scrolling past the
  // off-season dead weight.

  it("renders a jump chip per topic that scrolls to that topic's section (QU4)", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        topics: [
          STRUCTURED.topics[0],
          {
            ...STRUCTURED.topics[0],
            slug: "fantasy-football",
            title: "Fantasy football",
            items: [],
          },
        ],
      }),
    );
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Jump to topic" })).toBeInTheDocument();
    // Each section is an anchor target keyed by slug…
    const target = document.getElementById("fantasy-football");
    expect(target).not.toBeNull();
    // …and its chip scrolls to it (scrollIntoView is absent in jsdom — stub the target's).
    const scrolled = vi.fn();
    (target as HTMLElement).scrollIntoView = scrolled;
    fireEvent.click(screen.getByRole("button", { name: "Fantasy football" }));
    expect(scrolled).toHaveBeenCalled();
  });

  it("shows no chip row when only one topic rendered — nothing to skip (QU4)", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Jump to topic" })).not.toBeInTheDocument();
  });

  // FR4 audio chapters: the ~5-min cut is one featureless track — chapter chips seek to
  // each topic's word-count offset, landing 2s early so the spoken "Next up:" confirms
  // the jump. Offsets are estimates riding brief.chapters.json via BriefResponse.

  const CHAPTERED = {
    ...STRUCTURED,
    audio_available: true,
    audio_chapters: [
      { slug: "ai-llms", title: "AI / LLMs", start_seconds: 1 },
      { slug: "fantasy-football", title: "Fantasy football", start_seconds: 95.5 },
    ],
  };

  it("renders a seek chip per chapter that jumps the audio with a 2s lead-in (FR4)", async () => {
    briefWithMeta.mockResolvedValue(online(CHAPTERED));
    renderBrief();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const player = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(player, "currentTime", { value: 0, writable: true, configurable: true });
    player.play = vi.fn();

    fireEvent.click(screen.getByRole("button", { name: "Fantasy football" }));
    expect(player.currentTime).toBe(93.5); // 95.5 − 2s lead-in
    expect(player.play).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "AI / LLMs" }));
    expect(player.currentTime).toBe(0); // 1 − 2 clamps at the start, never negative
  });

  it("a cached pre-FR4 payload gets the player with no chips (FR4)", async () => {
    // A stale SW-cached BriefResponse has no audio_chapters key at all — the card must
    // render chip-free, not crash.
    briefWithMeta.mockResolvedValue(offline({ ...STRUCTURED, audio_available: true }));
    renderBrief();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const card = screen.getByText(/Listen to this brief/).closest("div")!;
    expect(within(card as HTMLElement).queryAllByRole("button")).toHaveLength(0);
  });

  // FR13: the developing badge finally names what changed — tapping it reveals the
  // digest as it read on first_seen day, verbatim (deterministic, bytes from disk).

  const DEVELOPING_ITEM = {
    ...ITEM,
    developing: true,
    first_seen: "2026-07-14",
    prior_digest: "OpenAI is weighing changes to the rolling cap.",
  };

  function withItem(item: unknown) {
    return {
      ...STRUCTURED,
      topics: [{ ...STRUCTURED.topics[0], items: [item] }],
    };
  }

  it("tapping the developing badge toggles the verbatim first-seen digest (FR13)", async () => {
    briefWithMeta.mockResolvedValue(online(withItem(DEVELOPING_ITEM)));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    const badge = screen.getByRole("button", { name: /developing · since Jul 14/ });
    expect(screen.queryByText(/OpenAI is weighing changes/)).not.toBeInTheDocument();
    fireEvent.click(badge);
    expect(screen.getByText(/As written Jul 14/)).toBeInTheDocument();
    expect(screen.getByText(/OpenAI is weighing changes to the rolling cap\./)).toBeInTheDocument();
    fireEvent.click(badge); // toggles back off
    expect(screen.queryByText(/OpenAI is weighing changes/)).not.toBeInTheDocument();
  });

  it("a developing item without prior_digest keeps the plain label (FR13)", async () => {
    // No prior digest on record (or a stale pre-FR13 cached payload) — the badge stays
    // the passive span it always was: no button, no empty disclosure, no crash.
    briefWithMeta.mockResolvedValue(
      online(withItem({ ...ITEM, developing: true, first_seen: "2026-07-14" })),
    );
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByText(/developing · since Jul 14/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /developing · since Jul 14/ }),
    ).not.toBeInTheDocument();
  });

  // FR2: stuck on stale, phone in hand — the stale banner's only recovery was a terminal
  // command the keyboard-less iPhone can't type. Now it's a tap: POST /brief/sweep, then
  // poll until the fresh brief lands.

  const STALE = { ...STRUCTURED, date: "2026-07-13" }; // past → the stale banner shows

  it("Refresh now kicks the sweep and polls for the fresh brief (FR2)", async () => {
    briefWithMeta.mockResolvedValue(online(STALE));
    sweepBrief.mockResolvedValue({ started: true, already_running: false });
    renderBrief();

    expect(await screen.findByText(/from a previous day/)).toBeInTheDocument();
    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByRole("button", { name: /Refresh now/ }));
      await act(async () => {});
      expect(sweepBrief).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Sweep started/)).toBeInTheDocument();
      // The poll: the page refetches on a timer until a newer date arrives.
      const callsBefore = briefWithMeta.mock.calls.length;
      await act(async () => {
        vi.advanceTimersByTime(30_000);
      });
      expect(briefWithMeta.mock.calls.length).toBeGreaterThan(callsBefore);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a tap while a sweep is already running says so honestly (FR2)", async () => {
    briefWithMeta.mockResolvedValue(online(STALE));
    sweepBrief.mockResolvedValue({ started: false, already_running: true });
    renderBrief();

    expect(await screen.findByText(/from a previous day/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Refresh now/ }));
    expect(await screen.findByText(/already running/)).toBeInTheDocument();
  });

  it("a failed kick shows an honest error and keeps the terminal path (FR2)", async () => {
    briefWithMeta.mockResolvedValue(online(STALE));
    sweepBrief.mockRejectedValue(new Error("sweep runner not found"));
    renderBrief();

    expect(await screen.findByText(/from a previous day/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Refresh now/ }));
    expect(await screen.findByText(/Couldn't start the sweep/)).toBeInTheDocument();
    // The manual fallback stays visible for the desktop case.
    expect(screen.getByText(/make sweep/)).toBeInTheDocument();
  });
});

// Mirror v0 (docs/ideas/the-mirror.md): the deterministic 'You this week' self-read the
// backend attaches to the LIVE payload — a strip atop the brief, an honest line below the
// signal floor, and nothing at all for a pre-Mirror cached payload.
const MIRROR = {
  generated_at: "now",
  window_days: 7,
  sufficient: true,
  sentence:
    "You showed up 4 of the last 7 mornings, left 3 notes, and asked 2 questions — attention leaned 44% AI / LLMs.",
  mornings: 4,
  notes: 3,
  asks: 2,
  news_events: 4,
  attention: [
    { slug: "ai-llms", title: "AI / LLMs", events: 4, share_pct: 44 },
    { slug: "local", title: "Local", events: 3, share_pct: 33 },
  ],
  paused_topics: ["Boston Celtics"],
};

describe("Mirror v0 — the 'You this week' strip", () => {
  it("renders the sentence, attention chips, and paused note when sufficient", async () => {
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, mirror: MIRROR }));
    renderBrief();

    expect(await screen.findByText("You this week")).toBeInTheDocument();
    expect(screen.getByText(MIRROR.sentence)).toBeInTheDocument();
    expect(screen.getByText("AI / LLMs 44%")).toBeInTheDocument();
    expect(screen.getByText("Local 33%")).toBeInTheDocument();
    expect(screen.getByText(/Paused: Boston Celtics/)).toBeInTheDocument();
  });

  it("shows the honest not-enough-signal line when insufficient", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        mirror: { ...MIRROR, sufficient: false, sentence: "", attention: [], paused_topics: [] },
      }),
    );
    renderBrief();

    expect(await screen.findByText("You this week")).toBeInTheDocument();
    expect(screen.getByText(/Not enough signal yet/)).toBeInTheDocument();
    expect(screen.queryByText(/attention leaned/)).not.toBeInTheDocument();
  });

  it("renders no strip for a payload without the field (stale SW-cached shape)", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.queryByText("You this week")).not.toBeInTheDocument();
  });
});

// Readiness v0 (docs/ideas/readiness-brief.md): the deterministic 'Coming up' projection
// the backend attaches to the LIVE payload — ranked multi-day trajectories, an honest
// line below two prior mornings of archive, a quiet line when nothing is in motion, and
// nothing at all for a pre-readiness cached payload.
const READINESS = {
  generated_at: "now",
  window_days: 7,
  history_days: 5,
  sufficient: true,
  items: [
    {
      slug: "ai-llms",
      title: "AI / LLMs",
      item_id: "abc123def456",
      headline: "OpenAI lifts caps",
      days_seen: 3,
      first_seen: "2026-07-14",
    },
    {
      slug: "celtics",
      title: "Boston Celtics",
      item_id: "fed654cba321",
      headline: "Tatum extension talks",
      days_seen: 2,
      first_seen: "2026-07-15",
    },
  ],
};

describe("Readiness v0 — the 'Coming up' strip", () => {
  it("renders ranked trajectory rows with badge-consistent since dates when sufficient", async () => {
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, readiness: READINESS }));
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Coming up" });
    expect(within(strip).getByText(/Multi-day stories still in motion/)).toBeInTheDocument();
    expect(within(strip).getByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(
      within(strip).getByText("AI / LLMs · seen 3 of the last 7 mornings · since Jul 14"),
    ).toBeInTheDocument();
    expect(within(strip).getByText("Tatum extension talks")).toBeInTheDocument();
    expect(
      within(strip).getByText("Boston Celtics · seen 2 of the last 7 mornings · since Jul 15"),
    ).toBeInTheDocument();
  });

  it("shows the honest not-enough-history line when insufficient", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        readiness: { ...READINESS, sufficient: false, history_days: 1, items: [] },
      }),
    );
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Coming up" });
    expect(within(strip).getByText(/Not enough sweep history yet/)).toBeInTheDocument();
    expect(within(strip).queryByText(/still in motion/)).not.toBeInTheDocument();
  });

  it("shows the quiet-morning line when sufficient but nothing is in motion", async () => {
    briefWithMeta.mockResolvedValue(
      online({ ...STRUCTURED, readiness: { ...READINESS, items: [] } }),
    );
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Coming up" });
    expect(
      within(strip).getByText("Nothing multi-day in motion this morning."),
    ).toBeInTheDocument();
    expect(within(strip).queryByText(/Multi-day stories still in motion/)).not.toBeInTheDocument();
  });

  it("renders no strip for a payload without the field (stale SW-cached shape)", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Coming up" })).not.toBeInTheDocument();
  });
});

// Calibrated Doubt v0 (docs/ideas/calibrated-doubt.md): the graded-wager record the
// backend attaches to the LIVE payload — yesterday's calls with ✓/✗ outcomes, the
// running record + Brier, a loud trial-week label while the lane is ungated (the
// assumption-4 gate made visible), an item chip for this morning's open wagers, and
// nothing at all for an empty record or a pre-calibration cached payload.
const CALIBRATION = {
  generated_at: "now",
  window_days: 7,
  resolved: 3,
  hits: 2,
  days: 2,
  brier: 0.15,
  trial: true,
  yesterday: [
    {
      slug: "ai-llms",
      title: "AI / LLMs",
      day: "2026-07-15",
      headline: "OpenAI lifts caps",
      prediction: "A rival answers within a day",
      confidence: 70,
      outcome: true,
    },
    {
      slug: "celtics",
      title: "Boston Celtics",
      day: "2026-07-15",
      headline: "Tatum extension talks",
      prediction: "Terms leak before the weekend",
      confidence: 60,
      outcome: false,
    },
  ],
};

describe("Calibrated Doubt v0 — the 'Yesterday's calls' strip", () => {
  it("renders graded calls with outcomes, the running record, and the trial label", async () => {
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, calibration: CALIBRATION }));
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Yesterday's calls" });
    expect(within(strip).getByText(/2-for-3 lifetime/)).toBeInTheDocument();
    expect(within(strip).getByText(/Brier 0\.15/)).toBeInTheDocument();
    expect(within(strip).getByText(/trial week/)).toBeInTheDocument();
    expect(within(strip).getByText("A rival answers within a day")).toBeInTheDocument();
    expect(
      within(strip).getByText("70% — AI / LLMs · OpenAI lifts caps · kept moving"),
    ).toBeInTheDocument();
    expect(within(strip).getByText("Terms leak before the weekend")).toBeInTheDocument();
    expect(
      within(strip).getByText("60% — Boston Celtics · Tatum extension talks · didn't move"),
    ).toBeInTheDocument();
  });

  it("drops the trial label once a graded week is on the books", async () => {
    briefWithMeta.mockResolvedValue(
      online({ ...STRUCTURED, calibration: { ...CALIBRATION, days: 7, trial: false } }),
    );
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Yesterday's calls" });
    expect(within(strip).getByText(/2-for-3 lifetime/)).toBeInTheDocument();
    expect(within(strip).queryByText(/trial week/)).not.toBeInTheDocument();
  });

  it("shows the quiet line when the record exists but the last morning made no calls", async () => {
    briefWithMeta.mockResolvedValue(
      online({ ...STRUCTURED, calibration: { ...CALIBRATION, yesterday: [] } }),
    );
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Yesterday's calls" });
    expect(
      within(strip).getByText("No calls to grade from the last morning."),
    ).toBeInTheDocument();
  });

  it("renders no strip when the record is empty (honest cold start)", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        calibration: {
          ...CALIBRATION,
          resolved: 0,
          hits: 0,
          days: 0,
          brier: null,
          yesterday: [],
        },
      }),
    );
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Yesterday's calls" })).not.toBeInTheDocument();
  });

  it("renders no strip for a payload without the field (stale SW-cached shape)", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();

    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Yesterday's calls" })).not.toBeInTheDocument();
  });

  it("shows this morning's open wager as a chip on its item", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        topics: [
          {
            ...STRUCTURED.topics[0],
            items: [{ ...ITEM, prediction: "A rival answers within a day", confidence: 65 }],
          },
        ],
      }),
    );
    renderBrief();

    expect(await screen.findByText(/65% call:/)).toBeInTheDocument();
    expect(screen.getByText("A rival answers within a day")).toBeInTheDocument();
  });
});

// Overnight Chief of Staff v0 (docs/ideas/overnight-chief-of-staff.md): the draft-only
// approve/discard queue pinned at the top of the live morning. Scope decisions from the
// 2026-07-20 gate: nothing sent or executed — approve saves a note through the existing
// notes path, discard is the undo; offline (cached payload) disables the write buttons
// like every other composer.
const OVERNIGHT = {
  generated_at: "now",
  date: "2099-01-01",
  proposals: [
    {
      id: "p1aaaaaaaaaa",
      type: "draft_note",
      slug: "ai-llms",
      title: "AI / LLMs",
      item_id: "abc123def456",
      item_headline: "OpenAI lifts caps",
      body: "Caps went away; watch the pricing response.",
      status: "proposed",
      note_id: null,
      created_at: "2099-01-01T11:05:00Z",
    },
    {
      id: "p2bbbbbbbbbb",
      type: "draft_note",
      slug: "celtics",
      title: "Boston Celtics",
      item_id: "def456abc123",
      item_headline: "Tatum talks",
      body: "Extension window opens; numbers drifting up.",
      status: "proposed",
      note_id: null,
      created_at: "2099-01-01T11:05:00Z",
    },
  ],
};

describe("Overnight v0 — the draft-only approve/discard queue", () => {
  it("renders the queue with drafts, verbs, and the nothing-was-sent reassurance", async () => {
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, overnight: OVERNIGHT }));
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Overnight" });
    expect(within(strip).getByText(/nothing was sent or executed/)).toBeInTheDocument();
    expect(within(strip).getByText("AI / LLMs · OpenAI lifts caps")).toBeInTheDocument();
    expect(
      within(strip).getByText("Caps went away; watch the pricing response."),
    ).toBeInTheDocument();
    expect(within(strip).getByText("Boston Celtics · Tatum talks")).toBeInTheDocument();
    expect(within(strip).getAllByRole("button", { name: "Approve" })).toHaveLength(2);
    expect(within(strip).getAllByRole("button", { name: "Discard" })).toHaveLength(2);
  });

  it("approve calls the API with the proposal id and flips the card to saved", async () => {
    briefWithMeta.mockResolvedValue(online({ ...STRUCTURED, overnight: OVERNIGHT }));
    approveOvernight.mockResolvedValue({
      ...OVERNIGHT.proposals[0],
      status: "approved",
      note_id: 7,
    });
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Overnight" });
    fireEvent.click(within(strip).getAllByRole("button", { name: "Approve" })[0]);

    expect(approveOvernight).toHaveBeenCalledWith("p1aaaaaaaaaa");
    expect(await within(strip).findByText("✓ Saved to notes")).toBeInTheDocument();
    // The resolved card keeps its draft visible but loses its verbs.
    expect(within(strip).getAllByRole("button", { name: "Approve" })).toHaveLength(1);
  });

  it("discard removes the card, and the strip once nothing visible remains", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        overnight: { ...OVERNIGHT, proposals: [OVERNIGHT.proposals[0]] },
      }),
    );
    discardOvernight.mockResolvedValue({ ...OVERNIGHT.proposals[0], status: "discarded" });
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Overnight" });
    fireEvent.click(within(strip).getByRole("button", { name: "Discard" }));

    expect(discardOvernight).toHaveBeenCalledWith("p1aaaaaaaaaa");
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Overnight" })).not.toBeInTheDocument(),
    );
  });

  it("renders already-resolved proposals as an after-action log", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        overnight: {
          ...OVERNIGHT,
          proposals: [
            { ...OVERNIGHT.proposals[0], status: "approved", note_id: 7 },
            { ...OVERNIGHT.proposals[1], status: "discarded" },
          ],
        },
      }),
    );
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Overnight" });
    expect(within(strip).getByText("✓ Saved to notes")).toBeInTheDocument();
    expect(within(strip).queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    // The discarded draft is gone, not displayed struck-through.
    expect(within(strip).queryByText("Boston Celtics · Tatum talks")).not.toBeInTheDocument();
  });

  it("shows a failure inline when a verb rejects, keeping the draft actionable", async () => {
    briefWithMeta.mockResolvedValue(
      online({
        ...STRUCTURED,
        overnight: { ...OVERNIGHT, proposals: [OVERNIGHT.proposals[0]] },
      }),
    );
    approveOvernight.mockRejectedValue(new Error("proposal already approved"));
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Overnight" });
    fireEvent.click(within(strip).getByRole("button", { name: "Approve" }));

    expect(await within(strip).findByText(/Couldn't save/)).toBeInTheDocument();
    expect(within(strip).getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("renders no strip for a payload without the field or with an empty queue", async () => {
    briefWithMeta.mockResolvedValue(online(STRUCTURED));
    renderBrief();
    expect(await screen.findByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Overnight" })).not.toBeInTheDocument();

    briefWithMeta.mockResolvedValue(
      online({ ...STRUCTURED, overnight: { ...OVERNIGHT, proposals: [] } }),
    );
    renderBrief();
    await waitFor(() => expect(briefWithMeta).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("region", { name: "Overnight" })).not.toBeInTheDocument();
  });

  it("disables the verbs on an offline cached payload — writes need the hub", async () => {
    briefWithMeta.mockResolvedValue(offline({ ...STRUCTURED, overnight: OVERNIGHT }));
    renderBrief();

    const strip = await screen.findByRole("region", { name: "Overnight" });
    for (const b of within(strip).getAllByRole("button", { name: "Approve" })) {
      expect(b).toBeDisabled();
    }
    for (const b of within(strip).getAllByRole("button", { name: "Discard" })) {
      expect(b).toBeDisabled();
    }
  });
});
