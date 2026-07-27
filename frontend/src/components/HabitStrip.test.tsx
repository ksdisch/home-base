import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BriefHabitResponse, BriefHabitWeek } from "../api/types";
import {
  consecutiveOnTarget,
  HabitStrip,
  highestMorningMilestone,
  isBestWeek,
  totalMornings,
} from "./HabitStrip";

const briefHabit = vi.fn();
vi.mock("../api/client", () => ({
  api: { briefHabit: () => briefHabit() },
}));

function wk(week_start: string, mornings: number, notes: number): BriefHabitWeek {
  return { week_start, mornings, notes };
}
function resp(weeks: BriefHabitWeek[]): BriefHabitResponse {
  return { generated_at: "now", weeks, last_graded: null };
}

beforeEach(() => {
  briefHabit.mockReset();
  localStorage.clear();
});

describe("HabitStrip milestone derivations — every marker is bound to a verified threshold", () => {
  it("totalMornings sums every week", () => {
    expect(totalMornings([wk("a", 5, 1), wk("b", 3, 0), wk("c", 4, 2)])).toBe(12);
    expect(totalMornings([])).toBe(0);
  });

  it("consecutiveOnTarget counts the trailing run of >=5-morning weeks and stops at a miss", () => {
    expect(consecutiveOnTarget([wk("a", 5, 0), wk("b", 5, 0), wk("c", 5, 0)])).toBe(3);
    expect(consecutiveOnTarget([wk("a", 5, 0), wk("b", 3, 0), wk("c", 5, 0)])).toBe(1);
    // an in-progress current week below target breaks the run — never premature
    expect(consecutiveOnTarget([wk("a", 5, 0), wk("b", 5, 0), wk("c", 2, 0)])).toBe(0);
    expect(consecutiveOnTarget([])).toBe(0);
  });

  it("isBestWeek needs >=2 prior weeks with mornings and a strictly better current week", () => {
    expect(isBestWeek([wk("a", 3, 0), wk("b", 4, 0), wk("c", 5, 0)])).toBe(true);
    expect(isBestWeek([wk("a", 3, 0), wk("b", 5, 0), wk("c", 5, 0)])).toBe(false); // tie, not strict
    expect(isBestWeek([wk("a", 4, 0), wk("b", 5, 0)])).toBe(false); // only 1 prior week
    expect(isBestWeek([wk("a", 0, 1), wk("b", 0, 2), wk("c", 1, 0)])).toBe(false); // <2 priors WITH mornings
  });

  it("highestMorningMilestone returns the largest crossed round threshold (0 when none)", () => {
    expect(highestMorningMilestone(0)).toBe(0);
    expect(highestMorningMilestone(24)).toBe(0);
    expect(highestMorningMilestone(25)).toBe(25);
    expect(highestMorningMilestone(150)).toBe(100);
    expect(highestMorningMilestone(400)).toBe(365);
  });
});

describe("HabitStrip line — earned markers only, default byte-for-byte unchanged", () => {
  it("leaves the current-week line unchanged when nothing is earned", async () => {
    briefHabit.mockResolvedValue(resp([wk("2026-06-29", 2, 1), wk("2026-07-06", 3, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("3 of 5 mornings");
    expect(container.textContent).toContain("1 of 3 notes");
    // none of the milestone markers may appear
    expect(container.textContent).not.toContain("✓");
    expect(container.textContent).not.toContain("weeks running");
    expect(container.textContent).not.toContain("best week");
    expect(container.textContent).not.toContain("☀");
  });

  it("marks the mornings target hit with an accent ✓ (mornings only)", async () => {
    briefHabit.mockResolvedValue(resp([wk("2026-06-29", 2, 1), wk("2026-07-06", 5, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("5 of 5 mornings ✓");
    // the accented element is the mornings fraction
    expect(container.querySelector(".text-accent")?.textContent).toContain("mornings");
  });

  it("adds the streak suffix once two+ weeks run on target", async () => {
    briefHabit.mockResolvedValue(resp([wk("2026-06-29", 5, 1), wk("2026-07-06", 5, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("2 weeks running");
  });

  it("celebrates a crossed lifetime-mornings milestone once, then never again (localStorage)", async () => {
    briefHabit.mockResolvedValue(resp([wk("2026-06-29", 50, 0), wk("2026-07-06", 50, 0)])); // total 100
    const first = render(<HabitStrip />);
    expect(await screen.findByText(/☀ 100 mornings/)).toBeInTheDocument();
    first.unmount();

    // second mount: localStorage now records the 100 milestone -> not celebrated again
    briefHabit.mockResolvedValue(resp([wk("2026-06-29", 50, 0), wk("2026-07-06", 50, 0)]));
    const second = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(second.container.textContent).not.toContain("☀ 100 mornings");
  });
});

// v14 visit-source attribution (docs/ideas/builder-vs-reader-metric.md): the raw morning
// count can't tell a Tuesday read from a localhost dev load, so the phone-sourced count
// rides BESIDE it. The criterion itself must not move — that's Kyle's call, not a silent
// side effect of shipping attribution.
describe("HabitStrip phone attribution — reported beside the raw count, never instead of it", () => {
  function wkp(
    week_start: string,
    mornings: number,
    mornings_phone: number,
    notes: number,
  ): BriefHabitWeek {
    return { week_start, mornings, mornings_phone, notes };
  }

  it("renders the phone-sourced count beside the raw one", async () => {
    briefHabit.mockResolvedValue(resp([wkp("2026-06-29", 4, 1, 1), wkp("2026-07-06", 3, 2, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("3 of 5 mornings");
    expect(container.textContent).toContain("(2 on phone)");
    // prior-week history carries it too — the fade shows up as a falling p, not a falling m
    expect(container.textContent).toContain("4m / 1p / 1n");
  });

  it("still renders the phone count at zero — the whole point is catching a fade", async () => {
    // A week that looks healthy on the raw number and is pure build exhaust underneath.
    briefHabit.mockResolvedValue(resp([wkp("2026-06-29", 5, 3, 1), wkp("2026-07-06", 5, 0, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("(0 on phone)");
  });

  it("leaves the v1 criterion on the RAW count — target ✓ ignores the phone number", async () => {
    briefHabit.mockResolvedValue(resp([wkp("2026-06-29", 2, 0, 1), wkp("2026-07-06", 5, 1, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("5 of 5 mornings ✓");
    expect(container.textContent).toContain("(1 on phone)");
    // the accent (target hit) is bound to the raw fraction, not the phone count
    expect(container.querySelector(".text-accent")?.textContent).toContain("mornings");
  });

  it("omits the phone count entirely on a pre-v14 payload", async () => {
    // An SW-cached response from before attribution shipped: no mornings_phone field.
    briefHabit.mockResolvedValue(resp([wk("2026-06-29", 2, 1), wk("2026-07-06", 3, 1)]));
    const { container } = render(<HabitStrip />);
    await screen.findByText(/Habit check/);
    expect(container.textContent).toContain("3 of 5 mornings");
    expect(container.textContent).not.toContain("on phone");
    expect(container.textContent).toContain("2m / 1n"); // history stays in the old shape
  });
});
