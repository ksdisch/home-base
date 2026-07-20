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
vi.mock("../api/client", () => ({
  api: {
    briefWithMeta: () => briefWithMeta(),
    logBriefVisit: () => logBriefVisit(),
    review: () => review(),
    courses: () => courses(),
    briefHabit: () => briefHabit(),
    addBriefNote: (body: unknown) => addBriefNote(body),
    deleteBriefNote: (id: number) => deleteBriefNote(id),
    briefAudioUrl: () => "/api/brief/audio",
    sweepBrief: () => sweepBrief(),
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
