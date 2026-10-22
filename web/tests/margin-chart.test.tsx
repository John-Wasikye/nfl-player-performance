import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarginHistoryChart, marginAxis, marginSeries } from "@/components/charts";
import type { GradedWeek } from "@/lib/types";

function week(n: number, mae: number, baselines: Record<string, number>, frozen: number | null = null): GradedWeek {
  return {
    season: 2026,
    week: n,
    player_games: 200,
    mae,
    rmse: mae * 1.3,
    interval_coverage: 0.8,
    baseline_mae: baselines,
    frozen_model_mae: frozen,
  };
}

const weeks = [
  week(5, 5.96, { recent_average: 5.98, season_average: 6.42, last_ten: 6.05 }),
  week(6, 5.05, { recent_average: 5.34, season_average: 5.41, last_ten: 5.24 }),
];

describe("margin series", () => {
  it("measures the model against the best baseline of each week, like the table does", () => {
    const [model] = marginSeries(weeks);
    expect(model.id).toBe("model");
    // Week 5's best is the recent average (5.98), week 6's is the last ten (5.24).
    expect(model.points.map((p) => p.week)).toEqual([5, 6]);
    expect(model.points[0].value).toBeCloseTo(0.02);
    expect(model.points[1].value).toBeCloseTo(0.19);
  });

  it("goes negative when the model loses to the baseline", () => {
    const [model] = marginSeries([week(3, 5.58, { recent_average: 5.44 })]);
    expect(model.points[0].value).toBeCloseTo(-0.14);
  });

  it("leaves the frozen control out until it has been graded", () => {
    expect(marginSeries(weeks).map((s) => s.id)).toEqual(["model"]);
  });

  it("adds the frozen control once a week has it, with gaps where it is missing", () => {
    const frozen = marginSeries([weeks[0], { ...weeks[1], frozen_model_mae: 5.2 }]).find((s) => s.id === "frozen");
    expect(frozen?.points[0].value).toBeNull();
    expect(frozen?.points[1].value).toBeCloseTo(0.04);
  });
});

describe("margin axis", () => {
  it("always shows the baseline and the 0.15 line, whatever the data", () => {
    const axis = marginAxis([0.02, 0.05]);
    expect(axis.min).toBeLessThanOrEqual(0);
    expect(axis.max).toBeGreaterThanOrEqual(0.15);
    expect(axis.ticks).toContain(0);
  });

  it("covers every value, including a loss", () => {
    const axis = marginAxis([-0.32, 0.41]);
    expect(axis.min).toBeLessThanOrEqual(-0.32);
    expect(axis.max).toBeGreaterThanOrEqual(0.41);
  });

  it("uses evenly spaced ticks and not too many of them", () => {
    const { ticks } = marginAxis([-0.32, 0.41]);
    expect(ticks.length).toBeLessThanOrEqual(7);
    const gaps = ticks.slice(1).map((t, i) => Math.round((t - ticks[i]) * 1000));
    expect(new Set(gaps).size).toBe(1);
  });
});

describe("margin history chart", () => {
  it("describes the latest week in words", () => {
    render(<MarginHistoryChart title="Margin over the best baseline" series={marginSeries(weeks)} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      /Model: 0\.19 points ahead of the best baseline in week 6/,
    );
  });

  it("says behind, not a negative number, when the model lost", () => {
    render(<MarginHistoryChart title="t" series={marginSeries([week(3, 5.58, { recent_average: 5.44 })])} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(/0\.14 points behind the best baseline in week 3/);
  });

  it("draws one line and one marker per graded week", () => {
    const { container } = render(<MarginHistoryChart title="t" series={marginSeries(weeks)} />);
    expect(container.querySelectorAll("path[data-series]")).toHaveLength(1);
    expect(container.querySelectorAll("circle")).toHaveLength(2);
  });

  it("labels the baseline, the too-close-to-call band, and which way is better", () => {
    render(<MarginHistoryChart title="t" series={marginSeries(weeks)} />);
    expect(screen.getByText("Baseline")).toBeInTheDocument();
    expect(screen.getByText("Too close to call")).toBeInTheDocument();
    expect(screen.getByText("Higher is better")).toBeInTheDocument();
  });

  it("renders nothing before any week is graded", () => {
    const { container } = render(<MarginHistoryChart title="t" series={marginSeries([])} />);
    expect(container).toBeEmptyDOMElement();
  });
});
