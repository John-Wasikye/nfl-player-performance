// Types for the published data contract (schema version 1). They mirror
// pipeline/nfl_pipeline/contract.py, which is the source of truth: change it there first.

export const SCHEMA_VERSION = 1;

export type Position = "QB" | "RB" | "WR" | "TE" | "K";
export const POSITIONS: readonly Position[] = ["QB", "RB", "WR", "TE", "K"];

export const POSITION_NAMES: Record<Position, string> = {
  QB: "Quarterbacks",
  RB: "Running backs",
  WR: "Wide receivers",
  TE: "Tight ends",
  K: "Kickers",
};

export type Component = "efficiency" | "production";

export interface CompositeView {
  score: number | null;
  efficiency: number | null;
  production: number | null;
  rank: number | null;
  rank_prev: number | null;
  movement: number | null; // previous rank minus current rank: positive means moved up
  is_new: boolean;
}

export interface FantasyView {
  points: number;
  per_game: number | null;
  rank: number;
  rank_prev: number | null;
  movement: number | null;
  is_new: boolean;
}

export interface RankedPlayer {
  player_id: string;
  name: string;
  team: string;
  injury_status: string | null;
  games: number;
  qualified: boolean; // false: listed but not ranked (too little volume)
  composite: CompositeView;
  fantasy: FantasyView;
}

export interface RankingsFile {
  schema_version: number;
  season: number;
  week: number;
  position: Position;
  week_complete: boolean;
  players: RankedPlayer[];
}

export interface BreakdownItem {
  metric: string;
  component: Component;
  value: number;
  percentile: number;
  weight: number;
  contribution_points: number;
}

export interface PlayerWeek {
  week: number;
  team: string;
  games: number;
  qualified: boolean;
  composite_rank: number | null;
  composite_score: number | null;
  efficiency_score: number | null;
  production_score: number | null;
  fantasy_rank: number;
  ppr_points: number;
}

export interface PlayerFile {
  schema_version: number;
  player_id: string;
  name: string;
  position: Position;
  team: string;
  season: number;
  latest_week: number;
  history: PlayerWeek[];
  breakdown: BreakdownItem[];
}

export interface Mover {
  player_id: string;
  name: string;
  team: string;
  rank: number;
  rank_prev: number;
  movement: number;
}

export interface MoversFile {
  schema_version: number;
  season: number;
  week: number;
  risers: Record<Position, Mover[]>;
  fallers: Record<Position, Mover[]>;
}

export interface MetricWeight {
  metric: string;
  component: Component;
  direction: "higher" | "lower";
  weight: number;
}

export interface PositionMethodology {
  position: Position;
  min_role_per_week: number;
  efficiency_weight: number;
  production_weight: number;
  metrics: MetricWeight[];
}

export interface BacktestHeadline {
  generated_at: string;
  tuning_seasons: number[];
  held_out_seasons: number[];
  selected_efficiency_weight: number;
  current_efficiency_weight: number;
  held_out_spearman: Record<
    Position,
    { selected: number | null; current: number | null; points_per_game_baseline: number | null }
  >;
}

export interface Methodology {
  schema_version: number;
  positions: PositionMethodology[];
  kicker_scoring: string;
  backtest: BacktestHeadline | null;
}

export interface Meta {
  schema_version: number;
  generated_at: string;
  pipeline_version: string;
  data_as_of: Record<string, string>;
  season: number;
  latest_week: number;
  week_complete: boolean;
  weeks: number[];
  positions: Position[];
}

export interface PredictedPlayer {
  player_id: string;
  name: string;
  team: string;
  opponent: string;
  is_home: boolean;
  position: Position;
  /** Points if he plays. */
  points: number;
  low: number;
  high: number;
  probability_of_playing: number;
  /** `points` discounted by the chance of playing. */
  expected_points: number;
  injury_status: string | null;
  /** "locked" once the week can no longer change. */
  status: "preliminary" | "locked";
  locked_at: string | null;
}

/** predictions/latest.json: which week the Predictions page shows. */
export interface PredictionsIndex {
  schema_version: number;
  generated_at: string;
  season: number;
  week: number;
  positions: Position[];
  status: "preliminary" | "locked";
  locked_at: string | null;
}

export interface PredictionsFile {
  schema_version: number;
  season: number;
  week: number;
  position: Position;
  generated_at: string;
  model_version: string;
  players: PredictedPlayer[];
}

/** `mae` only means something next to `player_games`. Don't compare it across different player groups. */
export interface GradedWeek {
  season: number;
  week: number;
  player_games: number;
  mae: number;
  rmse: number;
  interval_coverage: number;
  baseline_mae: Record<string, number>;
  /** A model frozen before the season, scored on the same games. */
  frozen_model_mae: number | null;
}

export interface AccuracyFile {
  schema_version: number;
  season: number;
  generated_at: string;
  weeks: GradedWeek[];
  season_to_date: GradedWeek | null;
  verdict: string;
}

export interface LedgerEntry {
  entry_id: string;
  proposed_at: string;
  hypothesis: string;
  change: string;
  champion_score: number;
  challenger_score: number;
  improvement: number;
  promoted: boolean;
  reason: string;
  /** Experiments that change which players are predicted are judged on margin over the baseline, not mean error. */
  metric: "mae" | "margin_over_baseline";
}

export interface LedgerFile {
  schema_version: number;
  generated_at: string;
  entries: LedgerEntry[];
}

export type RankView = "composite" | "fantasy";

export function isPosition(value: string): value is Position {
  return (POSITIONS as readonly string[]).includes(value);
}
