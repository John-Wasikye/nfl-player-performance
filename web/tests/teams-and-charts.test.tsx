import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { niceMax, rankTicks, RankHistoryChart, BreakdownBars } from "@/components/charts";
import { Avatar, MovementChip } from "@/components/ui";
import { backtestVerdict } from "@/components/MethodologyView";
import { contrastRatio, readableTextColor, TEAM_COLORS, teamColor } from "@/lib/teams";
import type { BacktestHeadline, BreakdownItem } from "@/lib/types";

describe("team colors", () => {
  it("has a color for all 32 teams and a fallback for anything else", () => {
    expect(Object.keys(TEAM_COLORS)).toHaveLength(32);
    expect(teamColor("KC")).toBe("#E31837");
    expect(teamColor("XXX")).toBe("#64748b");
  });

  it("picks white or black text, whichever reads better", () => {
    expect(readableTextColor("#0B162A")).toBe("#ffffff"); // navy
    expect(readableTextColor("#FFB612")).toBe("#0b0d12"); // gold
    expect(readableTextColor("#D3BC8D")).toBe("#0b0d12"); // tan
  });

  it("keeps every team avatar at a readable contrast (at least 3:1 for its large initials)", () => {
    for (const [team, color] of Object.entries(TEAM_COLORS)) {
      const text = readableTextColor(color);
      expect(contrastRatio(text, color), `${team} avatar`).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("avatar and movement chip", () => {
  it("shows the player's initials", () => {
    render(<Avatar name="Josh Allen" team="BUF" />);
    expect(screen.getByText("JA")).toBeInTheDocument();
  });

  it("describes movement in words, not just an arrow", () => {
    const { rerender } = render(<MovementChip movement={3} />);
    expect(screen.getByLabelText("Up 3 places")).toBeInTheDocument();
    rerender(<MovementChip movement={-1} />);
    expect(screen.getByLabelText("Down 1 place")).toBeInTheDocument();
    rerender(<MovementChip movement={0} />);
    expect(screen.getByLabelText("No change")).toBeInTheDocument();
  });

  it("marks a newly ranked player and shows nothing to compare when there is no previous rank", () => {
    const { rerender } = render(<MovementChip movement={null} isNew />);
    expect(screen.getByText("NEW")).toBeInTheDocument();
    rerender(<MovementChip movement={null} />);
    expect(screen.queryByText("NEW")).not.toBeInTheDocument();
  });
});

describe("chart axes", () => {
  it("rounds the axis up to a tidy number", () => {
    expect(niceMax(3)).toBe(5);
    expect(niceMax(8)).toBe(10);
    expect(niceMax(17)).toBe(20);
    expect(niceMax(37)).toBe(40);
    expect(niceMax(120)).toBe(125);
  });

  it("always includes rank 1 and the axis maximum as ticks", () => {
    for (const max of [5, 10, 20, 40, 125]) {
      const ticks = rankTicks(max);
      expect(ticks[0]).toBe(1);
      expect(ticks.at(-1)).toBe(max);
      expect(new Set(ticks).size).toBe(ticks.length);
    }
  });
});

describe("rank history chart", () => {
  const series = [
    {
      id: "composite",
      label: "Composite rank",
      color: "var(--accent)",
      points: [
        { week: 1, rank: 4 },
        { week: 2, rank: null },
        { week: 3, rank: 1 },
      ],
    },
  ];

  it("has a text description of where the player ended up", () => {
    render(<RankHistoryChart title="Josh Allen: rank by week" series={series} />);
    const chart = screen.getByRole("img");
    expect(chart).toHaveAccessibleName(/Composite rank: rank 1 in week 3/);
  });

  it("breaks the line where a week has no rank instead of drawing across the gap", () => {
    const { container } = render(<RankHistoryChart title="t" series={series} />);
    // Weeks 1 and 3 are separated by an unranked week 2, so there are two one-point segments.
    expect(container.querySelectorAll("path")).toHaveLength(2);
    expect(container.querySelectorAll("circle")).toHaveLength(2);
  });

  it("renders nothing when there is no rank at all", () => {
    const { container } = render(
      <RankHistoryChart title="t" series={[{ ...series[0], points: [{ week: 1, rank: null }] }]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("breakdown bars", () => {
  const items: BreakdownItem[] = [
    { metric: "epa_per_dropback", component: "efficiency", value: 0.462, percentile: 0.9, weight: 1, contribution_points: 12.6 },
    { metric: "cpoe", component: "efficiency", value: 6.9, percentile: 0.77, weight: 1, contribution_points: 10.8 },
    { metric: "passing_yards", component: "production", value: 582, percentile: 1, weight: 1, contribution_points: 7.5 },
  ];

  it("lists only the requested component, largest contribution first", () => {
    render(<BreakdownBars items={items} component="efficiency" />);
    const labels = screen.getAllByRole("meter").map((m) => m.getAttribute("aria-label"));
    expect(labels).toEqual(["EPA per dropback percentile", "CPOE percentile"]);
  });

  it("exposes each percentile to assistive technology", () => {
    render(<BreakdownBars items={items} component="production" />);
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText("100th pct")).toBeInTheDocument();
  });

  it("uses correct ordinals", () => {
    render(<BreakdownBars items={[{ ...items[0], percentile: 0.22 }]} component="efficiency" />);
    expect(screen.getByText("22nd pct")).toBeInTheDocument();
  });
});

describe("backtest verdict", () => {
  const base: BacktestHeadline = {
    generated_at: "2026-09-18T00:00:00Z",
    tuning_seasons: [2021, 2022, 2023],
    held_out_seasons: [2024, 2025],
    selected_efficiency_weight: 0.2,
    current_efficiency_weight: 0.7,
    held_out_spearman: {
      QB: { selected: 0.24, current: 0.23, points_per_game_baseline: 0.25 },
      RB: { selected: 0.47, current: 0.33, points_per_game_baseline: 0.5 },
      WR: { selected: 0.39, current: 0.28, points_per_game_baseline: 0.38 },
      TE: { selected: 0.33, current: 0.2, points_per_game_baseline: 0.31 },
      K: { selected: 0.08, current: 0.08, points_per_game_baseline: 0.1 },
    },
  };

  it("says so plainly when the current setting is worse where it matters", () => {
    const lines = backtestVerdict(base);
    expect(lines[0]).toMatch(/less accurately than fantasy points per game at RB, WR, TE/);
    expect(lines[1]).toMatch(/preferred setting was 20% efficiency/);
  });

  it("says the setting is worse everywhere when it is", () => {
    const worse = structuredClone(base);
    for (const p of Object.keys(worse.held_out_spearman) as Array<keyof typeof worse.held_out_spearman>) {
      worse.held_out_spearman[p].current = 0.05;
    }
    expect(backtestVerdict(worse)[0]).toMatch(/at every position/);
  });

  it("does not claim a problem when the current setting keeps up", () => {
    const fine = structuredClone(base);
    fine.selected_efficiency_weight = fine.current_efficiency_weight;
    for (const p of Object.keys(fine.held_out_spearman) as Array<keyof typeof fine.held_out_spearman>) {
      fine.held_out_spearman[p].current = fine.held_out_spearman[p].points_per_game_baseline;
    }
    const lines = backtestVerdict(fine);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatch(/about as well as/);
  });
});
