import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorHistoryChart, errorAxis, errorSeries } from "@/components/charts";
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

describe("error series", () => {
  it("compares the model with the best baseline of each week, like the table does", () => {
    const series = errorSeries(weeks);
    expect(series.map((s) => s.id)).toEqual(["model", "baseline"]);
    expect(series[0].points).toEqual([
      { week: 5, value: 5.96 },
      { week: 6, value: 5.05 },
    ]);
    // Week 5's best is the recent average, week 6's is the last ten.
    expect(series[1].points).toEqual([
      { week: 5, value: 5.98 },
      { week: 6, value: 5.24 },
    ]);
  });

  it("leaves the frozen control out until it has been graded", () => {
    expect(errorSeries(weeks).some((s) => s.id === "frozen")).toBe(false);
  });

  it("adds the frozen control once a week has it, with gaps where it is missing", () => {
    const withFrozen = [weeks[0], { ...weeks[1], frozen_model_mae: 5.2 }];
    const frozen = errorSeries(withFrozen).find((s) => s.id === "frozen");
    expect(frozen?.points).toEqual([
      { week: 5, value: null },
      { week: 6, value: 5.2 },
    ]);
  });
});

describe("error axis", () => {
  it("rounds out to whole points and keeps both ends as ticks", () => {
    const axis = errorAxis([5.05, 5.24, 5.96, 5.98]);
    expect(axis.min).toBe(5);
    expect(axis.max).toBe(6);
    expect(axis.ticks).toEqual([5, 5.5, 6]);
  });

  it("never collapses to a zero-height axis", () => {
    const axis = errorAxis([5, 5]);
    expect(axis.max).toBeGreaterThan(axis.min);
  });

  it("uses whole-point ticks on a wider range", () => {
    expect(errorAxis([4.2, 7.9]).ticks).toEqual([4, 5, 6, 7, 8]);
  });
});

describe("error history chart", () => {
  it("describes the latest week of each line in words", () => {
    render(<ErrorHistoryChart title="Average error by week" series={errorSeries(weeks)} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      /Model: 5\.05 points in week 6\. Best baseline: 5\.24 points in week 6/,
    );
  });

  it("draws one line and one marker per graded week for each series", () => {
    const { container } = render(<ErrorHistoryChart title="t" series={errorSeries(weeks)} />);
    expect(container.querySelectorAll("path[data-series]")).toHaveLength(2);
    expect(container.querySelectorAll("circle")).toHaveLength(4);
  });

  it("says that lower is better, since that is the opposite of the rank chart", () => {
    render(<ErrorHistoryChart title="t" series={errorSeries(weeks)} />);
    expect(screen.getByText("Lower is better")).toBeInTheDocument();
  });

  it("renders nothing before any week is graded", () => {
    const { container } = render(<ErrorHistoryChart title="t" series={errorSeries([])} />);
    expect(container).toBeEmptyDOMElement();
  });
});
