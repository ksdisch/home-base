import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
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

function renderBrief() {
  return render(
    <MemoryRouter>
      <Brief />
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
});
