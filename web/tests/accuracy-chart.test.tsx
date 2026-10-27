import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AccuracyHistoryChart, withinSeries } from "@/components/charts";
import type { GradedWeek } from "@/lib/types";

function week(n: number, within: number | undefined, baselines?: Record<string, number>): GradedWeek {
  return {
    season: 2026,
    week: n,
    player_games: 200,
    mae: 5.5,
    rmse: 7,
    interval_coverage: 0.8,
    baseline_mae: { recent_average: 5.6 },
    frozen_model_mae: null,
    within_5_points: within,
    baseline_within_5_points: baselines,
  };
}

const weeks = [
  week(5, 0.55, { recent_average: 0.53, season_average: 0.49, last_ten: 0.54 }),
  week(6, 0.62, { recent_average: 0.57, season_average: 0.56, last_ten: 0.58 }),
];

describe("within-5 series", () => {
  it("takes the model's share each week and the best simple average's share on the same players", () => {
    const [model, baseline] = withinSeries(weeks);
    expect(model.points).toEqual([
      { week: 5, value: 0.55 },
      { week: 6, value: 0.62 },
    ]);
    // Week 5's best simple average is the last ten, week 6's is the last ten again.
    expect(baseline.points).toEqual([
      { week: 5, value: 0.54 },
      { week: 6, value: 0.58 },
    ]);
  });

  it("leaves a gap for a week graded before the figure existed", () => {
    const [model] = withinSeries([week(4, undefined), ...weeks]);
    expect(model.points[0]).toEqual({ week: 4, value: null });
  });
});

describe("frozen model line", () => {
  it("is left off until a week has a frozen forecast", () => {
    expect(withinSeries(weeks).map((s) => s.id)).toEqual(["model", "baseline"]);
  });

  it("appears once a week has one, with gaps for weeks locked before it existed", () => {
    const later = { ...week(7, 0.6, { recent_average: 0.55 }), frozen_within_5_points: 0.57 };
    const frozen = withinSeries([...weeks, later]).find((s) => s.id === "frozen");
    expect(frozen?.label).toBe("Frozen model");
    expect(frozen?.points).toEqual([
      { week: 5, value: null },
      { week: 6, value: null },
      { week: 7, value: 0.57 },
    ]);
  });
});

describe("accuracy history chart", () => {
  it("labels both axes", () => {
    render(<AccuracyHistoryChart title="t" series={withinSeries(weeks)} />);
    expect(screen.getByText("Week")).toBeInTheDocument();
    expect(screen.getByText("Projections within 5 points")).toBeInTheDocument();
  });

  it("runs the vertical axis from 0% to 100% and labels every week", () => {
    render(<AccuracyHistoryChart title="t" series={withinSeries(weeks)} />);
    for (const label of ["0%", "20%", "40%", "60%", "80%", "100%", "5", "6"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("describes the latest week in words", () => {
    render(<AccuracyHistoryChart title="Projections within 5 points, by week" series={withinSeries(weeks)} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      /Model: 62% within 5 points in week 6\. Best simple average: 58% within 5 points in week 6/,
    );
  });

  it("draws one line and one marker per graded week for each series", () => {
    const { container } = render(<AccuracyHistoryChart title="t" series={withinSeries(weeks)} />);
    expect(container.querySelectorAll("path[data-series]")).toHaveLength(2);
    expect(container.querySelectorAll("circle")).toHaveLength(4);
  });

  it("says that higher is better", () => {
    render(<AccuracyHistoryChart title="t" series={withinSeries(weeks)} />);
    expect(screen.getByText("Higher is better")).toBeInTheDocument();
  });

  it("draws at the width it is shown at, so the labels stay readable on a phone", () => {
    const original = globalThis.ResizeObserver;
    globalThis.ResizeObserver = class {
      constructor(private callback: ResizeObserverCallback) {}
      observe() {
        this.callback([{ contentRect: { width: 320 } } as ResizeObserverEntry], this as unknown as ResizeObserver);
      }
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
    try {
      render(<AccuracyHistoryChart title="t" series={withinSeries(weeks)} />);
      expect(screen.getByRole("img").getAttribute("viewBox")).toMatch(/^0 0 320 /);
    } finally {
      globalThis.ResizeObserver = original;
    }
  });

  it("renders nothing until a week has the figure", () => {
    const { container } = render(<AccuracyHistoryChart title="t" series={withinSeries([week(5, undefined)])} />);
    expect(container).toBeEmptyDOMElement();
  });
});
