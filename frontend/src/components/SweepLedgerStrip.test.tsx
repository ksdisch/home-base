import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SweepLedgerStrip } from "./SweepLedgerStrip";
import type { BriefRunDay } from "../api/types";

const briefRunsSummary = vi.fn();
vi.mock("../api/client", () => ({
  api: { briefRunsSummary: (days?: number) => briefRunsSummary(days) },
}));

function day(date: string, over: Partial<BriefRunDay> = {}): BriefRunDay {
  return {
    date,
    topics: 9,
    errors: 0,
    cost_usd: 8.12,
    duration_ms: 1_260_000,
    ran: true,
    thin: false,
    ...over,
  };
}

function summary(over: Partial<Parameters<typeof briefRunsSummary>[0]> = {}) {
  const days = [day("2026-07-26"), day("2026-07-25"), day("2026-07-24")];
  return {
    generated_at: "now",
    latest: days[0],
    days,
    window_days: 7,
    cost_usd: 24.36,
    errors: 0,
    missing_days: 0,
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // A fixed "today" so "this morning" vs a named date is deterministic.
  vi.setSystemTime(new Date(2026, 6, 26, 9, 0, 0));
});

describe("SweepLedgerStrip", () => {
  it("totals the morning into one ops line", async () => {
    briefRunsSummary.mockResolvedValue(summary());
    render(<SweepLedgerStrip />);

    const line = await screen.findByTestId("sweep-ledger-line");
    expect(line).toHaveTextContent("9 topics");
    expect(line).toHaveTextContent("21 min");
    expect(line).toHaveTextContent("$8.12");
    expect(line).toHaveTextContent("0 errors");
  });

  it("says 'this morning' only when the latest run really is today", async () => {
    briefRunsSummary.mockResolvedValue(summary());
    render(<SweepLedgerStrip />);
    expect(await screen.findByTestId("sweep-ledger-line")).toHaveTextContent(/this morning/i);
  });

  it("names the day instead when today hasn't swept yet", async () => {
    const days = [day("2026-07-26", { ran: false, topics: 0, cost_usd: 0 }), day("2026-07-25")];
    briefRunsSummary.mockResolvedValue(summary({ latest: days[1], days, missing_days: 1 }));
    render(<SweepLedgerStrip />);

    const line = await screen.findByTestId("sweep-ledger-line");
    expect(line).not.toHaveTextContent(/this morning/i);
    expect(line).toHaveTextContent(/Jul 25/);
  });

  it("surfaces a missing day in the roll-up", async () => {
    const days = [day("2026-07-26"), day("2026-07-25", { ran: false, topics: 0, cost_usd: 0 })];
    briefRunsSummary.mockResolvedValue(summary({ days, missing_days: 1 }));
    render(<SweepLedgerStrip />);

    const rollup = await screen.findByTestId("sweep-ledger-rollup");
    expect(rollup).toHaveTextContent(/no sweep/i);
    expect(rollup).toHaveTextContent(/Jul 25/);
  });

  it("marks a day that ran but came in far under the norm", async () => {
    const days = [day("2026-07-26"), day("2026-07-25", { cost_usd: 1.2, thin: true, topics: 2 })];
    briefRunsSummary.mockResolvedValue(summary({ days }));
    render(<SweepLedgerStrip />);

    const rollup = await screen.findByTestId("sweep-ledger-rollup");
    expect(rollup).toHaveTextContent(/thin/i);
  });

  it("a healthy week gets no warnings at all", async () => {
    briefRunsSummary.mockResolvedValue(summary());
    render(<SweepLedgerStrip />);
    await screen.findByTestId("sweep-ledger-line");

    const rollup = screen.getByTestId("sweep-ledger-rollup");
    expect(rollup).not.toHaveTextContent(/thin/i);
    expect(rollup).not.toHaveTextContent(/no sweep/i);
  });

  it("errors are called out, not buried", async () => {
    briefRunsSummary.mockResolvedValue(
      summary({ latest: day("2026-07-26", { errors: 2 }), errors: 2 }),
    );
    render(<SweepLedgerStrip />);
    expect(await screen.findByTestId("sweep-ledger-line")).toHaveTextContent("2 errors");
  });

  it("renders nothing on an empty ledger — never an empty ops line", async () => {
    briefRunsSummary.mockResolvedValue(summary({ latest: null, days: [], cost_usd: 0 }));
    const { container } = render(<SweepLedgerStrip />);
    await waitFor(() => expect(briefRunsSummary).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the fetch fails — it must never block the morning read", async () => {
    briefRunsSummary.mockRejectedValue(new Error("offline"));
    const { container } = render(<SweepLedgerStrip />);
    await waitFor(() => expect(briefRunsSummary).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
