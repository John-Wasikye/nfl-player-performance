# Backtest: does rank predict next week?

Generated 2026-09-18T20:04:26.966632+00:00. Does the rank at week N predict what a player does in week N+1?

The efficiency weight was chosen on the tuning seasons (2021, 2022, 2023) and checked on the held-out seasons (2024, 2025).
Selection rule: the highest efficiency weight whose average Spearman across positions on the tuning seasons is within 0.005 of the best (near-ties go to more efficiency).

## How to read the numbers

- **Spearman**: rank correlation between the ranking score at week N and the outcome in week N+1, averaged over every week. 0 means no relationship; 1 would be perfect. Single-game player results are very noisy, so modest values are expected.
- **Lift**: extra next-week points the top-ranked players scored versus the average ranked player (top 12 QB/TE/K, top 24 RB/WR).
- Only players ranked at week N who played in week N+1 are counted.
- The two baselines are simple: rank by season fantasy points, or by points per game.

## Next-week fantasy points (the outcome used to choose the weight)

Average across positions.

| Method | Tuning Spearman | Tuning lift | Held-out Spearman | Held-out lift |
|---|---|---|---|---|
| Composite, 0% efficiency | 0.294 | 2.12 | 0.302 | 2.11 |
| Composite, 20% efficiency (chosen) | 0.294 | 2.11 | 0.304 | 2.14 |
| Composite, 40% efficiency | 0.279 | 1.97 | 0.287 | 2.01 |
| Composite, 50% efficiency | 0.262 | 1.92 | 0.274 | 1.87 |
| Composite, 60% efficiency | 0.239 | 1.73 | 0.253 | 1.69 |
| Composite, 70% efficiency (current) | 0.213 | 1.49 | 0.226 | 1.58 |
| Composite, 80% efficiency | 0.188 | 1.37 | 0.197 | 1.31 |
| Composite, 100% efficiency | 0.139 | 1.04 | 0.143 | 1.00 |
| Baseline: season fantasy points | 0.283 | 2.07 | 0.300 | 2.05 |
| Baseline: fantasy points per game | 0.294 | 2.06 | 0.308 | 2.12 |

## Next-week EPA (an efficiency-flavored outcome)

Total EPA created next week. Kickers have no EPA, so this averages QB, RB, WR, and TE.

| Method | Tuning Spearman | Held-out Spearman |
|---|---|---|
| Composite, 0% efficiency | 0.116 | 0.129 |
| Composite, 20% efficiency (chosen) | 0.125 | 0.138 |
| Composite, 40% efficiency | 0.127 | 0.142 |
| Composite, 50% efficiency | 0.129 | 0.144 |
| Composite, 60% efficiency | 0.126 | 0.141 |
| Composite, 70% efficiency (current) | 0.122 | 0.137 |
| Composite, 80% efficiency | 0.118 | 0.132 |
| Composite, 100% efficiency | 0.109 | 0.115 |
| Baseline: season fantasy points | 0.111 | 0.125 |
| Baseline: fantasy points per game | 0.109 | 0.124 |

## Held-out results by position (fantasy points)

Standard error is over weeks. Weeks in one season are not independent, so treat it as a rough guide.

| Position | Weeks | Chosen | Current | Per-game baseline |
|---|---|---|---|---|
| QB | 34 | 0.244 ± 0.032 | 0.234 ± 0.032 | 0.253 ± 0.038 |
| RB | 34 | 0.475 ± 0.020 | 0.328 ± 0.023 | 0.500 ± 0.017 |
| WR | 34 | 0.392 ± 0.021 | 0.279 ± 0.021 | 0.379 ± 0.021 |
| TE | 34 | 0.331 ± 0.025 | 0.207 ± 0.027 | 0.308 ± 0.030 |
| K | 34 | 0.076 ± 0.041 | 0.080 ± 0.047 | 0.102 ± 0.044 |

## Composite minus the per-game baseline (held-out, Spearman, paired by week)

A positive difference means the composite ranked next week's results better than simply ranking by fantasy points per game.

| Position | Chosen | Current |
|---|---|---|
| QB | -0.009 ± 0.019 | -0.019 ± 0.022 |
| RB | -0.025 ± 0.009 | -0.172 ± 0.017 |
| WR | 0.013 ± 0.009 | -0.100 ± 0.013 |
| TE | 0.022 ± 0.012 | -0.101 ± 0.029 |
| K | -0.026 ± 0.021 | -0.022 ± 0.028 |

## Held-out Spearman by point in the season (fantasy points, average across positions)

Efficiency rates rest on few plays early in a season, so the picture can change by week.

| Weeks | Composite, 20% efficiency (chosen) | Composite, 70% efficiency (current) | Baseline: fantasy points per game | Baseline: season fantasy points |
|---|---|---|---|---|
| weeks 1-5 | 0.247 | 0.163 | 0.239 | 0.227 |
| weeks 6-11 | 0.298 | 0.234 | 0.311 | 0.301 |
| weeks 12+ | 0.356 | 0.269 | 0.363 | 0.359 |
