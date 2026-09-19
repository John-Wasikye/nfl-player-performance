# Where the model missed: 2026 week 1

244 graded player-games. Average error 5.739 against 5.910 for the best simple baseline (margin +0.170).

## By position

| position_group | players | model | baseline | margin |
|---|---|---|---|---|
| K | 29 | 3.35 | 3.68 | 0.32 |
| QB | 33 | 6.97 | 6.47 | -0.51 |
| RB | 51 | 7.03 | 6.96 | -0.07 |
| TE | 46 | 5.17 | 5.45 | 0.29 |
| WR | 85 | 5.61 | 6.07 | 0.46 |

## By how much the player had recently been scoring

| tier | players | model | baseline | margin |
|---|---|---|---|---|
| 4-8 | 84 | 4.41 | 4.39 | -0.02 |
| 8-13 | 78 | 5.39 | 5.58 | 0.19 |
| 13+ | 82 | 7.43 | 7.78 | 0.35 |

## The ten biggest misses

Individually these are mostly noise — a single game is not evidence. They are here to
read for a *pattern*, and a pattern is only worth proposing if it can be written as a
feature that would have been computable before kickoff.

| player | pos | projected | actual | error |
|---|---|---|---|---|
| Jalen Coker | WR | 8.42 | 33.80 | 25.38 |
| Kenneth Walker III | RB | 10.52 | 34.10 | 23.58 |
| Christian Watson | WR | 9.95 | 32.70 | 22.75 |
| Isaiah Likely | TE | 5.60 | 27.80 | 22.20 |
| David Montgomery | RB | 7.42 | 28.90 | 21.48 |
| D'Andre Swift | RB | 11.69 | 32.40 | 20.71 |
| Caleb Williams | QB | 17.02 | 37.26 | 20.24 |
| Justin Jefferson | WR | 11.56 | 31.20 | 19.64 |
| Ashton Jeanty | RB | 14.50 | 32.70 | 18.20 |
| Bryce Young | QB | 13.34 | 31.44 | 18.10 |

## What has not been tried

Datasets in the warehouse that no feature currently uses:
  - fct_player_week_advanced: yards before/after contact, pressure rate, play-action and motion
    rates, screen and no-huddle rates
  - stg_ngs: separation, cushion, air-yards share, time to throw, stacked-box rate
  - stg_participation: personnel groupings and who was on the field (TRAINING ONLY - it is a
    post-season release and can never be available for a live week)
  - depth_charts: listed role, which is not the same as snap share

## The bar

A candidate ships only if it beats the champion by more than 0.05 mean absolute error
on a walk-forward replay and keeps interval coverage between 0.75 and 0.85. Most will
not. The research already ruled out adaptive weights, per-player bias correction and
role-change heuristics, so do not propose those again; they are in the ledger.