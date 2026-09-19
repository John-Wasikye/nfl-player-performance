# Predicting Weekly NFL Player Performance

I ran every analysis below on five regular seasons of nflverse data, 2021 to 2025. The code is in `research/` in the project repo and the raw results are in `research/results/`.

Sections 1 to 5.14 are the research I did before writing any prediction code, to find out how much room there was. Sections 5.15 and 5.16 came afterwards, when the first full run of the finished engine missed the bar I had set for it.

---

## 1. Summary

I wanted to predict each player's next game for QB, RB, WR, TE and K. Injured players had to be left out, home and away had to count, and if I used AI it had to keep improving without costing more than a Claude Pro plan. Before building anything I measured how much of that was possible. Here is what I found.

1. **A player's recent usage does most of the work.** Adding everything else I could think of (betting lines, opponent, weather, injury tags) moved the explained variance of next-game fantasy points from 0.27 to only 0.29. A single game is noisy, and my best models explain about 29% of it.
2. **Volume is predictable, yards somewhat, touchdowns barely.** Held-out R²: carries 0.44 (RB), targets 0.31 (WR), attempts 0.23 (QB); yards 0.12 to 0.29; touchdowns 0.00 to 0.09. Interceptions can't be predicted. A player's recent touchdown total predicted worse than the league average did, so touchdowns have to be treated as small probabilities driven by opportunity.
3. **Home-field advantage is real but small, and I found no stable "loud stadium" effect.** Players score about 0.5 points (4.8%) more at home, quarterbacks about 1.3 (8.1%). Neither a stadium's effect on visitors nor a team's home edge repeated between 2021-23 and 2024-25 (correlations 0.11, -0.25 and -0.04, none significant). Kansas City, often called the loudest stadium, was near the bottom for visiting false starts.
4. **Wind and cold matter for the game, not for the individual player.** Wind of 15+ mph cut passing efficiency and game scoring (about 4.8 fewer total points), but adding weather to the per-player model made it slightly worse.
5. **The betting line is well calibrated.** Implied team points track actual points (slope 1.02, r = 0.40). Favorites run more plays, and underdogs pass about 4 points more often.
6. **A simple model is nearly as good as a complex one.** Ridge regression reached R² 0.280, gradient boosting 0.288 and their average 0.289, against 0.232 for a plain recent average. The limit comes from the data, not the algorithm.
7. **Injury reports are informative.** Players listed Out played 0.1% of the time and Doubtful 0.4%. Questionable players played 63% of the time (quarterbacks 35%).
8. **Ranges need calibrating.** Raw quantile models covered 77% of outcomes for an 80% interval, and a conformal correction brought that to 79.7%. The typical 80% range is about 17 fantasy points wide.
9. **There is little headroom, and the error isn't clustered.** An oracle that knew each player's true season-long average would score MAE 5.074 against my model's 5.445, a gap of 6.8%. Error is spread evenly across situations. Returning players, new teams and changed roles are all predicted better than average. Reading the injury text I have doesn't help either (AUC 0.672 to 0.663).
10. **"The model gets smarter every week" turned out to be false, at least in the usual sense.** Retraining every week beat a frozen model by only 0.037 MAE (0.7%), and the gap didn't grow as the season went on (trend +0.00003 per week). Adaptive ensemble weights, per-position bias correction, per-player bias learning and role-change heuristics all made predictions worse. Even an oracle that knew each player's true bias in advance would gain only 0.17 MAE (3%).
11. **Who you predict matters as much as how.** The first full run of the built engine beat the baseline by 0.052, well under the 0.15 I had set as the bar. The model was losing to a plain average on low-volume players (margin -0.291 for players averaging under 2 points, -0.093 from 2 to 4) and winning clearly on players with a real role (+0.292 for those averaging 13 or more). The margin rises steadily across all six scoring tiers. Restricting projections to players averaging at least 4 points over their last five games clears the bar and still covers 8,464 of 12,388 player-games. Raw MAE goes up under this restriction, because better players are more variable, so only the margin can be compared across populations.
12. **Where the restriction is applied matters.** Training on everyone and publishing only the eligible players beats dropping the low-volume players entirely (+0.170 against +0.159), but it pushed interval coverage down to 0.778. Split conformal prediction only guarantees coverage when the calibration set looks like what is being predicted, and low-volume players have unusually small errors. Calibrating on the published population restored coverage to 0.797 with identical MAE to four decimal places. The final result is a margin of +0.170 against the 0.15 bar, with none of the gain coming from a better model.

The design that follows from this is a simple ensemble of a regularized linear model and gradient boosting, prediction ranges instead of single numbers, and a rule that nothing goes into the model unless it beats the current one on weeks neither was trained on.

On the AI question: the evidence rules out the versions where an LLM produces or adjusts the numbers. It supports one mechanism, LLM-driven feature engineering, which has published evidence of improving tabular models (CAAFE improved 11 of 14 datasets, with mean ROC AUC going from 0.798 to 0.822). It works best where the domain has a lot of meaning in it, and football does. There is also nflverse data I haven't used yet, which is the most likely place for the last 6.8%. So Claude's job is to read each week's failures and write feature code against that data, and an automated test decides whether the code goes in. No number on the site comes from Claude.

---

## 2. Questions

1. How predictable is a single NFL game for a player, by stat?
2. Which factors add predictive value beyond a player's own history?
3. How large is home-field advantage for players, and does it differ by stadium?
4. How should injuries and availability be handled?
5. Which model families work best, and how should uncertainty be reported?
6. Where can an LLM add value without breaking the cost limit or making things up?

---

## 3. Background

**Home-field advantage.** NFL home teams have historically won about 57% (2009-2015 regular seasons; [Bleacher Report summary](https://bleacherreport.com/articles/2656748-how-the-nfl-cheats-home-field-advantage)). In 2020, with empty stadiums, home teams finished 127-128-1, the first sub-.500 home record in NFL history ([The Ringer](https://www.theringer.com/2021/01/06/nfl/nfl-playoffs-home-field-advantage-covid-19-restrictions)). One natural-experiment analysis put a full crowd at about +1.6 points of margin, roughly half of the home advantage ([Davis and Krieger, SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3914238); I only saw this through a search summary, not the full text). The crowd-noise mechanism is debated. Visiting teams have committed record false starts in loud games, but a 2023 study of penalties with and without crowds found that offensive false starts were not affected, while pre-snap defensive penalties against the home team fell when crowds were present ([Farnell 2023](https://journals.sagepub.com/doi/full/10.1177/15270025221148997), abstract via search summary). Travel and rest also seem to matter, with mixed evidence on time zones ([Sports Insights](https://www.sportsinsights.com/blog/is-there-still-a-disadvantage-for-nfl-west-coast-teams-traveling-east/)).

**Stability of statistics.** Usage persists and efficiency and touchdowns don't. Target share correlates about 0.70 from year to year and yards per route run above 0.60 ([SumerSports](https://sumersports.com/the-zone/sticky-football-stats-predictive-nfl-metrics/)). Touchdown rate is unstable, with only 6 of 112 receivers at a 15%+ rate repeating it (industry analysis via [search](https://www.si.com/nfl/2018/08/01/fantasy-football-2018-most-predictable-wide-receiver-stats)). Expected-touchdown models score each carry and target by field position instead of trusting a player's own touchdown count ([Fantasy Points xTD](https://www.fantasypoints.com/nfl/articles/2023/xtd-touchdown-regression-candidates)).

**Expected fantasy points.** nflverse's own `ffopportunity` models opportunity with xgboost trained on public play-by-play, estimating what an average player would score given the situation ([ffopportunity](https://ffopportunity.ffverse.com/)). I use the same opportunity-first idea.

**Game script and the betting market.** Favorites outscore underdogs at every position, even though underdogs take a slightly higher share of the passing. The practical lesson is to "target points, not game script" ([Fantasy Footballers analysis](https://www.thefantasyfootballers.com/articles/the-fantasy-football-mythbusters-flip-the-game-script/)). Implied team totals turn spread and total into expected points, but say nothing about which player gets the work ([Sharp Football](https://www.sharpfootballanalysis.com/fantasy/nfl-implied-team-totals-tool/)).

**Opponent matchups.** Defense-versus-position rankings are contaminated by opponent quality, game script and small samples, and wide receiver and tight end matchups are especially unstable ([discussion](https://github.com/CommonFox/going-deep/issues/132)).

**Weather.** Published analyses report passing efficiency falling sharply above about 20 mph wind, and scoring about 5% lower in 25-50 F games ([summary of studies](https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=1982&context=cmc_theses)).

**Injuries and teammates.** Targets get redistributed when a top receiver is out, but unevenly, and running back workloads are more predictable than receiver targets ([UCLA Bruin Sports Analytics](https://www.bruinsportsanalytics.com/post/wr_target_dist)).

**Models and ensembles.** Gradient boosting and random forests are the standard for weekly fantasy prediction. Ensembles of many projection sources beat individual sources, and a simple average beat individual sources in 63% of head-to-head comparisons ([Fantasy Football Analytics](https://fantasyfootballanalytics.net/which-projections-are-most-accurate)). A hierarchical Bayesian projection model with partial pooling matched a 7-game average on error (MAE 6.08 vs 5.99), and its value was in calibrated uncertainty ([write-up](https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence/)). Counts such as touchdowns are over-dispersed relative to Poisson in general and are handled with negative binomial or Tweedie models ([survey](https://arxiv.org/pdf/1908.08764)).

**Uncertainty and validation.** Conformalized quantile regression gives distribution-free interval coverage ([Romano et al.](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf)). Time-ordered (walk-forward) validation is needed because ordinary cross-validation leaks future information ([overview](https://machinelearningmastery.com/backtest-machine-learning-models-time-series-forecasting/)).

**LLMs.** On tabular and time-series prediction, gradient boosting stays competitive or better once there is a reasonable amount of data, and LLMs help mainly when there is very little ([survey](https://arxiv.org/pdf/2402.17944); [GBDT vs LLM few-shot](https://arxiv.org/abs/2411.04324)). So the numbers come from a statistical model, and Claude's part is elsewhere (section 7.6).

**Claude and cost.** A Claude Pro subscription does not include API usage, which is billed separately per token ([Claude Help Center](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console)). Claude Code shares usage limits with claude.ai, and a set `ANTHROPIC_API_KEY` makes it bill the API instead of the subscription ([Claude Help Center](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)).

**A gap in the literature.** I couldn't find a trustworthy published accuracy ceiling for weekly player projections, so I measured one.

---

## 4. Data

- **In use:** nflverse weekly player stats, play-by-play (about 49,000 plays per season), schedules (spreads, totals, roof, wind, temperature, rest days), injuries, snap counts and rosters. All analyses use regular seasons 2021-2025. The 2026 season is in progress.
- **Added later:** weekly advanced stats (Pro Football Reference, 2018+) and Next Gen Stats went into the feature store. Play charting (FTN, 2022+) is ingested but isn't a model feature yet. The who-was-on-the-field data (2016-2025) is published only after a season ends, so it can train a model but can never be available for a live week.
- **Not available:** crowd noise or attendance, player prop lines, official inactive lists before kickoff, and stadium coordinates. I haven't built a stadium table.
- **Method note.** Analyses of player outcomes use only games a player appeared in, and only players averaging at least 4 fantasy points over their last 5 games. That is deliberate, because availability is modelled separately.

---

## 5. Empirical studies on my data

### 5.1 Home-field advantage and loud stadiums (`a_home_advantage.py`, `a4_team_home_edge.py`)

**Team level (1,333 non-neutral games).** Home teams outscored visitors by 2.06 points per game (SE 0.39) and won 53.9%. By season the margin ranged from 1.6 to 2.7. Offensive EPA per play differed by only 0.003 (SE 0.008), so the points edge doesn't show up clearly in per-play efficiency.

**Player level (same player at home versus away, at least 4 games each, 1,278 player-seasons).**

| Position | Home minus away (points per game) | SE | Percent of average |
|---|---|---|---|
| QB | +1.28 | 0.32 | 8.1% |
| RB | +0.46 | 0.21 | 4.1% |
| WR | +0.50 | 0.17 | 4.8% |
| TE | +0.10 | 0.24 | 1.1% (not significant) |
| K | +0.42 | 0.18 | 5.2% |
| All | +0.53 | 0.10 | 4.8% |

**Is there a "loud stadium" effect?** I tested visiting offenses at 30 stadiums, about 42 visits each.

- False starts by the visiting team averaged 1.80 per 100 snaps. Stadiums differ more than chance would predict (chi-square 49.4, 29 degrees of freedom, p = 0.010), and visiting offensive efficiency also varied (F = 1.65, p = 0.016).
- The differences didn't repeat. Comparing 2021-23 with 2024-25 across the same stadiums, the correlation was +0.11 for false-start rate (p = 0.55) and -0.25 for visiting EPA (p = 0.18). A real stadium trait should correlate positively.
- Team home edges (home margin minus road margin) didn't repeat either: correlation -0.04 (2021-23 vs 2024-25) and -0.06 (odd vs even seasons). The spread across teams (SD 2.9 points) was no larger than luck alone would produce (3.1).
- The folklore doesn't hold up. Kansas City visitors committed 1.16 false starts per 100 snaps, among the lowest. Seattle had 2.21 (top six) but the smallest home-versus-road margin gap of any team (-0.6 points). The highest visiting false-start rates were Cleveland, Pittsburgh, Miami, Dallas, Tennessee and Seattle.
- Domes versus open air made no difference (1.76 vs 1.83 false starts per 100; visiting EPA +0.004, p = 0.69).

**Conclusion.** I model a league-wide home effect by position (about +5%, quarterbacks +8%) and don't hard-code stadium reputations. If I add stadium-specific effects, they'll need empirical-Bayes shrinkage and a held-out test each season. My proxies (false starts, EPA) are indirect, because no decibel data exists.

### 5.2 Which statistics are skill and which are luck (`b_stability_and_touchdowns.py`)

Year-to-year correlations, for players with enough volume in both seasons:

| Position | Usage | Efficiency | Touchdown rate |
|---|---|---|---|
| WR | targets per game 0.71, target share 0.70 | yards per target 0.28, catch rate 0.47 | 0.12 |
| TE | targets per game 0.58 | yards per target 0.36, catch rate 0.20 | 0.17 |
| RB | carries per game 0.48, targets per game 0.65 | yards per carry 0.17 | 0.09 |
| QB | attempts per game 0.64, rush yards per game 0.85 | yards per attempt 0.35 | 0.40 (interception rate 0.01) |

Odd-versus-even-week reliability (full-season equivalent) told the same story: usage 0.85 to 0.91, efficiency 0.3 to 0.7, touchdown rates 0.2 to 0.5.

### 5.3 Touchdowns (`b_stability_and_touchdowns.py`)

- Counts are close to Poisson. The variance-to-mean ratio of touchdowns per game was 1.04 to 1.15.
- Field position drives scoring. Rushing touchdown rates by distance: 55% at the 1-yard line, 24% at 4-5 yards, 12% at 6-10, 5% at 11-20, 1% at 21-40. The small buckets are noisy and would need smoothing.
- Predicting the next game's touchdowns (2024-25, trailing 6 games): the correlation was 0.22 with trailing expected touchdowns, 0.20 with trailing touches and 0.18 with trailing actual touchdowns. Even the best explains only about 5% of the variance. About 33% of player-games have a touchdown.

### 5.4 Which factors help next-game fantasy points? (`d_context_ablation.py`)

LightGBM trained on 2021-23 (10,516 player-games) and tested on 2024-25 (7,445), using only features known before kickoff:

| Model | MAE | R² |
|---|---|---|
| Recent-average baseline (exponential) | 5.670 | 0.232 |
| + player history and usage | 5.457 | 0.273 |
| + game context (implied total, spread, home, rest, week) | 5.439 | 0.283 |
| + opponent points allowed to position | 5.441 | 0.283 |
| + weather | 5.460 | 0.283 |
| + injury status (of players who played) | 5.465 | 0.285 |

Removing a group from the full model raised error by: history +1.18, opponent +0.005, game context +0.003, injury tag -0.005, weather -0.023. History dominates, and the rest is small or noise at this data size. That doesn't prove the other factors are useless. They may matter for touchdowns, extreme games or structured models. It does mean each one has to earn its place on a held-out test.

### 5.5 Model families and ranges (`e_models_and_components.py`)

| Model | MAE | R² |
|---|---|---|
| Recent-average baseline | 5.670 | 0.232 |
| Ridge regression | 5.480 | 0.280 |
| LightGBM | 5.440 | 0.288 |
| Average of ridge and LightGBM | 5.441 | 0.289 |

For the 80% prediction range, raw quantile models covered 77.2% of outcomes, and after a conformal correction they covered 79.7%. The ranges are wide, about 16.7 fantasy points.

### 5.6 How predictable is each stat? (held-out R², model versus trailing average)

| Stat | R² | Notes |
|---|---|---|
| RB carries | 0.44 | volume |
| WR targets | 0.31 | volume |
| TE targets | 0.28 | volume |
| QB attempts | 0.23 | volume |
| RB rush yards | 0.29 | |
| QB pass yards | 0.24 | |
| WR receiving yards | 0.18 | |
| TE receiving yards | 0.14 | |
| RB receiving yards | 0.12 | |
| QB passing touchdowns | 0.09 | |
| RB rushing touchdowns | 0.04 | trailing average alone: -0.04 |
| WR receiving touchdowns | 0.02 | trailing average alone: -0.10 |
| TE receiving touchdowns | -0.01 | |
| QB interceptions | -0.10 | unpredictable |

### 5.7 Weather (`d_context_ablation.py`, outdoor games with recorded weather)

- Wind (EPA per dropback): 0-9 mph +0.045 (n = 509 games), 10-14 mph +0.017 (180), 15+ mph -0.041 (88, SE 0.025).
- Total points: 45.2 (0-9 mph), 42.7 (10-14), 40.4 (15+), about 4.8 fewer.
- Temperature (EPA per dropback): below 40 F -0.001, 40-59 F +0.020, 60+ F +0.049.
- Field goals: no clear drop in make rate after adjusting for distance, because teams avoid long kicks in wind. The effect shows up as fewer attempts and fewer points, not lower accuracy.

### 5.8 Game script and the line (`d_context_ablation.py`)

| Team spread | Pass rate | Plays | Points |
|---|---|---|---|
| Underdog 7+ | 59.4% | 59.5 | 17.4 |
| Underdog 3-7 | 59.4% | 62.0 | 20.3 |
| Pick'em | 57.5% | 61.9 | 21.6 |
| Favorite 3-7 | 56.3% | 62.5 | 25.9 |
| Favorite 7+ | 55.4% | 63.4 | 28.7 |

Implied team total against actual points gives r = 0.40, slope 1.02 and intercept -0.3 over 2,718 team-games, which is well calibrated.

### 5.9 Teammates (`d_context_ablation.py`)

When a team's top receiver was ruled out (145 team-games), the next three receiving options averaged +0.20 targets against their trailing average, compared with -0.29 when he played. That is a difference of about +0.5 targets each, or roughly 1.5 extra targets shared among three players.

### 5.10 Injury reports and availability (2021-2025)

| Report status | Actually played |
|---|---|
| Out | 0.1% |
| Doubtful | 0.4% |
| Questionable | 63% (QB 35%, K 63%, RB 64%, TE 66%, WR 67%) |
| Questionable, full practice | 71% |
| Questionable, limited practice | 65% |
| Questionable, did not practice | 43% |

### 5.11 Does the system get smarter week by week? (`f_weekly_learning.py`)

I replayed 2024 and 2025 one week at a time (36 weeks, 7,445 player-games), and in each week the model could only see games played before it. Mean absolute error, lower is better:

| Strategy | MAE | vs frozen |
|---|---|---|
| Recent-average baseline | 5.670 | -0.187 |
| Frozen (trained once on 2021-23, never updated) | 5.483 | - |
| Retrained every week on everything so far | 5.446 | +0.037 |
| Retrain + per-position bias correction (last 4 weeks of errors) | 5.448 | +0.035 |
| Retrain + adaptive ensemble weights (last 6 weeks) | 5.476 | +0.007 |

- Weekly retraining is worth about 0.7%. One week adds roughly 200 rows to a 10,000-row training set, and the model is already close to what the data can support.
- The gap doesn't grow. The trend in (frozen minus adaptive) across the 36 weeks is +0.00003 per week, which is flat. A system that was compounding would fan out over the season.
- Adaptive ensemble weights hurt. They drifted toward equal weighting, including 32% on the naive baseline, which means they were fitting six weeks of noise.
- The model's edge over the baseline shrinks as the season goes on, the opposite of what I expected. Skill was +0.276 MAE in weeks 1-4, +0.172 in weeks 5-9, +0.202 in weeks 10-13 and +0.140 from week 14. Late in the season a simple trailing average is already close to the model, because each player's own history has become informative. The model's advantage is largest when data is scarce.

### 5.12 Do player-level learning mechanisms work? (`g_player_learning.py`)

Same walk-forward setup, testing the mechanisms that "learning about each player" usually means:

| Mechanism | MAE | vs base |
|---|---|---|
| Base (retrained ensemble) | 5.446 | - |
| + each player's own recent over/under-performance, shrunk | 5.507 | -0.061 |
| + role-change detection (recent usage shift) | 5.546 | -0.100 |
| + both | 5.634 | -0.188 |

- Every mechanism made predictions worse. About 168 players per week had enough history for a bias estimate and 66 were flagged as role changes, so this isn't an artifact of a small sample.
- The ceiling is low even with hindsight. An oracle that knew each player's true average bias across 2024-2025 and applied it shrunk would gain only 0.17 MAE (about 3%). There is very little player-specific bias left for any mechanism to find.

### 5.13 Where does the model fail, and is the failure reachable? (`h_error_anatomy.py`)

If the error were concentrated in situations I could name before kickoff, a layer built for those situations would have something to aim at. It isn't.

| Segment (all known before kickoff) | Share of games | Share of error | MAE inside | MAE outside |
|---|---|---|---|---|
| Volatile recent scoring | 25.0% | 28.4% | 6.18 | 5.20 |
| Returning after missing a week | 23.4% | 21.7% | 5.04 | 5.57 |
| Big usage shift | 26.2% | 24.1% | 5.02 | 5.60 |
| Listed Questionable | 4.3% | 4.3% | 5.36 | 5.45 |
| Thin history (<= 6 games) | 4.0% | 4.0% | 5.40 | 5.45 |
| New team | 2.7% | 2.7% | 5.41 | 5.45 |
| Any of the above | 59.8% | 59.1% | 5.38 | 5.54 |

- Every segment carries almost exactly its proportional share of the error, and the union carries slightly less than its share. The situations that look hard to a person (a player returning, a changed role, a new team) are ones the model already handles. Only volatile players are harder, and that is close to circular.
- The error is spread across games rather than clustered. The worst 25% of player-games hold 52.7% of total error, which is about what any heavy-tailed outcome produces.
- An oracle that knew each player's true season-long average in advance would post MAE 5.074, and my model posts 5.445. The gap between a working model and perfect knowledge of every player's level is 0.371 MAE (6.8%), and much of that is game-to-game randomness that nobody could predict.

### 5.14 Can reading text improve availability calls? (`i_availability.py`)

Availability looked like the obvious place for a text-reading layer, because a wrong call costs a player's whole score (about 8.2 points) instead of the usual 5.4-point error. The sample is 2,347 Questionable player-weeks.

| Model | AUC | Brier |
|---|---|---|
| Base rate (always predict "plays") | - | 0.2493 |
| Practice status, position, player history | 0.672 | 0.2274 |
| + injury type from the report text | 0.663 | 0.2293 |

- Adding the injury description made it slightly worse (AUC -0.009). Play rates do vary by body part (hamstring 50%, hip 66%), but practice status already carries that information.
- The injury text nflverse publishes is a body part, not the richer reporting ("expected to be a game-time decision", "will be on a snap count") that would actually help. I don't have that text, and the text I do have is used up.

**What 5.11 to 5.14 add up to.** The idea that an adaptive system improves week over week isn't supported here. Weekly self-adjustment fits noise faster than signal at this sample size. Any adaptation has to earn its place on held-out evidence, and the default is off. Section 7.5 is built around this result.

### 5.15 Who should actually be predicted? (`j_population.py`, `k_train_wide_publish_narrow.py`)

The first full walk-forward run of the built engine came in at 4.458 mean absolute error against a best baseline of 4.510. That is a margin of 0.052, well short of the 0.15 I had set as the bar, so the engine would not have passed its own promotion gate.

Before reaching for a better model, I asked a cheaper question: was the margin being diluted by players nobody needs a projection for? Splitting the graded player-games by how much each player had recently been scoring answers it.

| Recent scoring (`ppr_mean5`) | Player-games | Mean actual | Model MAE | Baseline MAE | Margin |
|---|---|---|---|---|---|
| 0-2 | 2,131 | 1.89 | 2.222 | 1.931 | -0.291 |
| 2-4 | 1,814 | 3.76 | 3.349 | 3.256 | -0.093 |
| 4-6 | 1,593 | 5.44 | 3.986 | 4.052 | +0.067 |
| 6-9 | 2,196 | 7.87 | 4.691 | 4.793 | +0.102 |
| 9-13 | 2,161 | 10.36 | 5.500 | 5.678 | +0.178 |
| 13+ | 2,494 | 15.15 | 6.390 | 6.681 | +0.292 |

The model was losing to a simple average on the bottom two tiers, which made up 32% of the graded population. A deep-bench player who scores near zero every week is easy to predict, and the model only adds variance to a question the average already answers. That lost ground cancelled out real gains at the top.

The same split by position shows the same thing:

| Position | Player-games | Model MAE | Baseline MAE | Margin |
|---|---|---|---|---|
| QB | 1,255 | 6.361 | 6.681 | +0.320 |
| K | 1,041 | 3.865 | 4.010 | +0.145 |
| RB | 3,071 | 4.353 | 4.418 | +0.065 |
| TE | 2,374 | 3.707 | 3.687 | -0.020 |
| WR | 4,670 | 4.529 | 4.517 | -0.011 |

Quarterbacks do best because almost every graded quarterback is a starter with a real role. Tight ends and receivers do worst because those positions have the longest tails of low-volume players.

Then I re-ran the whole harness at a series of cut-offs:

| Eligible if `ppr_mean5` at least | Player-games | MAE | Baseline | Margin | Coverage | Clears 0.15 |
|---|---|---|---|---|---|---|
| 0 | 12,388 | 4.463 | 4.515 | +0.052 | 0.797 | no |
| 2 | 10,278 | 4.931 | 5.047 | +0.116 | 0.797 | no |
| 4 | 8,464 | 5.278 | 5.436 | +0.159 | 0.798 | yes |
| 6 | 6,879 | 5.586 | 5.752 | +0.166 | 0.799 | yes |
| 8 | 5,421 | 5.850 | 6.018 | +0.168 | 0.801 | yes |
| 10 | 4,037 | 6.136 | 6.346 | +0.210 | 0.798 | yes |

Raw MAE rises with the cut-off, from 4.463 to 6.136. The model isn't getting worse. Higher-scoring players are just more variable, so absolute errors are bigger. Each row is a different population, so comparing MAE across rows means nothing, and only the margin over the baseline within a row can be compared. This affects how I publish too. The headline accuracy figure will look worse after this change, and the Report card has to explain why.

**Is this gaming the metric?** It would be if I had searched thresholds until one passed. Two things argue against that. I expected the direction beforehand, since the design already called for restricting to players with a real role, and this measured it rather than discovering it. And the margin rises steadily across all six independent tiers. A cherry-picked cut-off doesn't produce a smooth gradient, and a real effect does. I chose 4 because it is the smallest value that clears the bar, which keeps the largest audience. At 10 the margin is better, but two thirds of players would have no projection.

**Where the threshold is applied.** Experiment J filtered the data before the harness saw it, so it dropped low-volume players from training as well as from grading. Those are two separate questions. "Nobody needs this projection" is a product decision. "The model learns worse from these rows" is an empirical claim, and it points the other way, since more training data usually helps. Experiment K ran both on identical graded rows:

| | Player-games | MAE | Margin | Coverage |
|---|---|---|---|---|
| Trained narrow (low-volume players dropped entirely) | 8,464 | 5.278 | +0.159 | 0.798 |
| Trained wide (dropped only from publishing) | 8,464 | 5.266 | +0.170 | 0.778 |

Training on everyone is better for accuracy, as expected. But it pulled interval coverage down to 0.778, at the edge of the acceptable band.

### 5.16 Why coverage dropped, and the fix (`l_calibration_population.py`)

The drop in coverage wasn't noise. Split conformal prediction guarantees coverage only when the calibration set is exchangeable with what is being predicted. Low-volume players have small errors, because scores near zero are easy to get right. Calibrating on a population full of them produces a correction that is too small for the players I actually publish, and the ranges come out too narrow.

That points to its own fix: train on everything, but calibrate on the population that will be published. Experiment L tested it.

| Calibrated on | MAE | Margin | Coverage | Mean range width |
|---|---|---|---|---|
| Everyone | 5.2659 | +0.1704 | 0.778 | 15.85 |
| The published population | 5.2659 | +0.1704 | 0.797 | 16.14 |

MAE is identical to four decimal places, which is the check that the change did what I said it did. Calibration moves the range and never the point estimate. Coverage comes back to 0.797 against a nominal 0.80, at the cost of ranges about 0.3 points wider.

The final configuration:

- Train on every player-week with at least 3 prior games.
- Calibrate the ranges on the publishable population only.
- Publish only players averaging at least 4 points over their last five games (section 5.15).

The final held-out result is MAE 5.266 against a best baseline of 5.436, a margin of +0.170 on a 0.15 bar, with 0.797 interval coverage over 8,464 player-games. The engine passes its own promotion gate. The first honest measurement of the built system was a margin of 0.052, so this is a little over three times the original edge, and none of it came from a better model. It came from being precise about which players are predicted and which population the ranges are calibrated on.

---

## 6. Design principles

1. **Opportunity first.** Predict volume, then efficiency, then touchdowns, rather than only the final number.
2. **Shrink hard where luck dominates.** Efficiency, and especially touchdown and interception rates, should move toward position and situation averages. Usage should move less.
3. **Put each factor where it works.** Betting lines and weather set the team's scoring environment. Usage shares and teammate availability divide it among players. Home advantage is a small league-wide multiplier.
4. **Simple plus flexible.** Average a regularized linear model with gradient boosting, and keep the naive average as a baseline.
5. **Distributions, not points.** Quantile models with conformal calibration.
6. **Every factor earns its place** on held-out walk-forward tests and is dropped if it doesn't.
7. **Adaptation is a hypothesis.** Sections 5.11 and 5.12 showed the usual weekly self-adjustment tricks making things worse. Nothing adaptive ships unless it beats the static model on locked, out-of-sample predictions.

---

## 7. What I built

### 7.1 What is predicted

The site publishes PPR fantasy points (standard scoring for kickers) with an 80% range, and for players who might not play, the chance that they take the field. I originally planned to predict the components too (targets, carries, yards, touchdown probabilities). I haven't built that. Section 5.6 shows why it is the harder problem, since yards and especially touchdowns are much less predictable than volume.

**For whom** (sections 5.15 and 5.16). A player is projected if he has at least 3 prior games and has averaged at least 4 PPR points over his last five. Below that line the model was measured losing to the player's own recent average, so publishing those projections would be worse than publishing nothing. The three populations are deliberately different. The model trains on every player-week with 3 prior games, calibrates its ranges on the publishable population only, and publishes the eligible players. That is roughly 280 players per week across the five positions.

### 7.2 Availability and injured players

- **Excluded:** players listed Out or Doubtful are dropped instead of shown at zero, because a zero reads as "he will play badly" when I mean "he isn't playing". Anyone not on the active roster for that week is left out too.
- **Questionable:** the projection is for if he plays, and the chance that he does is estimated from practice participation, with a base rate of 63% and a much lower one for quarterbacks. The projection and the chance are shown separately.
- **Late scratches** (announced about 90 minutes before kickoff) aren't treated as misses. A player who doesn't take the field isn't graded against the points model.
- **Teammate effect:** a top receiver being out shifts targets to the next options (section 5.9). I measured this but haven't built it into the model.

### 7.3 The model

The point estimate is an average of a ridge regression and a LightGBM model. The 80% range comes from two more LightGBM models fitted to the 10th and 90th percentiles, widened by a split-conformal correction measured on weeks the quantile models never saw. The code refuses to calibrate on rows the model was trained on, since that would make every published range too narrow without any visible error.

The features fall into six groups: recent form, usage, advanced-stats and Next Gen Stats measures, game context (implied total, spread, home, rest, week), weather, and the opponent's points allowed to the position. Every feature is computed from games before the one being predicted, and there are tests that change a future week's result and check that earlier features don't move.

I planned a layered structure (team environment, then volume shares, then efficiency, then touchdowns) and built the direct ensemble instead. Sections 5.4 and 5.5 showed little room for extra structure to help, and the layers would have been a lot of code to maintain. I haven't tested whether that judgment was right.

Weather for upcoming games is a known weakness. The schedule only records wind and temperature after a game is played, and I haven't connected a forecast source yet, so those two features are filled with typical values for games that haven't happened.

### 7.4 Home and away

Home is a feature in the model, so the league-wide effect from section 5.1 is learned from data. There is no stadium-specific or team-specific term, for the reasons in 5.1.

### 7.5 How the system gets better over time

Sections 5.11 and 5.12 set the constraint. Every mechanism that nudged predictions automatically from recent errors made things worse, and even perfect hindsight about a player's bias was worth only 3%. So the system doesn't tune itself week to week. It improves through a governed experiment loop: someone proposes a hypothesis, it gets tested on held-out data, and it ships only if it wins.

**Tier 1, features update themselves.** Each week adds a game to every player's history, so the inputs sharpen on their own. That is the biggest week-to-week effect, but it isn't the model learning, and the recent-average baseline gets the same benefit, so I don't count it as improvement.

**Tier 2, weekly retraining.** It is worth about 0.7% and doesn't compound (5.11). It's free and harmless so it stays, and it matters more across seasons than within one.

**Tier 3, calibration.** Interval coverage drifts as scoring environments change, so the ranges are recalibrated each time projections are generated. This targets coverage and honesty rather than point accuracy, and it is judged on coverage.

**Tier 4, the experiment ledger.** This is the part that can compound. A candidate change goes through the walk-forward harness against the current model. It might be a new feature or data source, a structural change, or a rule such as how hard to shrink a metric. Every candidate is recorded with its hypothesis, the measured result and the decision, and the ledger is published on the Report card. I'd expect roughly 18 graded experiments over a season.

**The promotion gate.** A change ships only if it beats the current model on weeks neither was trained on, by more than the noise, and keeps interval coverage inside 0.75 to 0.85. Two details came out of using it:

- Candidates are scored on the population the site publishes, not on everyone. Scoring over everyone dilutes a change that helps exactly the players on the site by about a third.
- Champion and challenger are scored on identical rows, so the per-row difference in absolute error has a standard error. Its mean equals the difference of the two error rates. A change under two standard errors from zero is rejected however large the raw margin looks.

The ledger currently has four entries: the three population experiments from 5.15 and 5.16, and one feature candidate. That candidate was a ratio of recent form to season average. It came in at 0.08 standard errors from zero, with 49.99% of rows improved, which is a coin flip, and it was rejected.

### 7.6 Where Claude fits

**What the evidence rules out.** Claude can't make point predictions much better by producing or adjusting numbers. Section 5.13 puts the total headroom at 6.8%, sections 5.11 and 5.12 show self-tuning failing, 5.14 shows the available injury text is used up, and the literature in section 3 has gradient boosting ahead of LLMs on tabular prediction once there is real data. Any design where an LLM writes or nudges the predicted number works against all four.

**What the evidence supports.** There is one mechanism with published evidence of an LLM measurably improving a tabular model, and that is LLM-driven feature engineering. CAAFE ([Hollmann et al., NeurIPS 2023](https://arxiv.org/abs/2305.03403)) has an LLM write feature code from a dataset description and keeps a feature only if it improves validation performance. It improved 11 of 14 datasets and lifted mean ROC AUC from 0.798 to 0.822, which the authors compare to switching from logistic regression to a random forest. LLM-FE ([TMLR 2026](https://arxiv.org/pdf/2503.14434)) extends this into an evolutionary loop where measured performance feeds the next proposal.

There is a documented caveat. LLMs tend to produce too many trivially simple features, and they help most when the domain has real meaning in it instead of being an anonymous numeric table ([Kuken et al.](https://arxiv.org/pdf/2410.17787)). Football is the favorable case. "Snap share trend relative to the team's other backs", "air yards share since the WR1 was injured" and "depth chart position change" mean something to anyone who knows the sport and nothing to a model that only sees column names.

**Data I haven't used.** The models in section 5 used weekly box-score history, schedule context and a defensive-strength summary. FTN charting and depth charts still aren't features. The charting has play-level detail such as play action and motion, and depth charts give the listed role, which isn't the same as snap share. That is the most likely place for the last 6.8%.

**How it works day to day.** `nfl-pipeline experiment` writes a report of where the model missed most recently, split by position and by how much each player had been scoring, along with which datasets are unused. I give that to Claude Code, which writes one candidate feature with a stated hypothesis and adds it to a registry. Running `nfl-pipeline experiment --run <name>` puts it through the gate and records the result. A candidate is refused before it is scored if it reads the outcome, drops or reorders rows, or redefines an existing feature. The outcome check runs the candidate a second time with the answer blanked out and compares.

Claude never produces, adjusts or overrides a published number. Its influence reaches the site only as code that passed the gate. A rejected candidate stays in the registry, because deleting it would invite proposing the same thing again.

**What to expect.** The realistic target is capturing part of the 0.371 MAE of headroom. CAAFE's published gain was comparable to changing model families, and here that would mean a few percent. I'm not claiming that AI predicts football better than anyone. The claim is that an automated, audited search for improvement runs over data nobody has mined yet, and the system is built so that accuracy can only ratchet upward. That can be checked week by week on the Report card.

**Cost.** The pipeline makes no API calls, so there is no per-token billing. A Pro subscription doesn't cover API usage (section 3), and `ANTHROPIC_API_KEY` is never set, because that would silently switch Claude Code to paid API billing. One short session a week fits inside the plan's shared limits. If a session never happens, predictions still publish and the ledger just doesn't advance that week.

### 7.7 Weekly loop

Tuesday: grade last week, retrain, publish preliminary predictions. Before each game: refresh injuries and lines, then lock, with Thursday games locking earlier in the week. Locked predictions are timestamped and never edited. At the moment I run this by hand. Scheduling it is part of the AWS deployment, which I haven't done yet, so no week has been locked and graded so far.

### 7.8 Evaluation

- **Protocol:** walk-forward across 2021-2025 (never train on the future), plus live weekly grading.
- **Baselines:** recent average, season average, and last ten games.
- **Metrics:** MAE and RMSE, rank correlation, interval coverage (target 78-82% for 80% intervals), and margin over the baseline.
- **Bars to clear on held-out seasons:** beat the recent-average baseline by at least 0.15 MAE, keep intervals covering 78-82%, and show no leakage. The tests prove that future results can't change past predictions.
- **The bar is measured on the population I publish** (section 5.15), and that population is fixed before the season. Raw MAE depends on which players are included, so every accuracy figure is reported next to its player count, and the model is compared only with baselines scored on the same rows.
- **The learning claim is itself measured.** The Report card is meant to carry a control line from a model frozen at the start of the season. If the experiment loop isn't beating that model, the site should say so. I haven't fitted the frozen model yet, so for now the Report card says it has no basis to claim improvement.
- **Reporting:** a public Report card with weekly accuracy against baselines and the range hit rate, with misses left visible. If accuracy is flat, the site says so.

### 7.9 Limitations

- The ceiling is about 0.29 R² for fantasy points and 0.05 to 0.09 for touchdowns. Week-to-week accuracy will wobble.
- Weekly improvement may be small or absent. My tests found weekly self-adjustment worth 0.7% at best and often negative. I expect a season's experiments to yield a few percent in total, with several negative results along the way.
- My factor tests use a modest, untuned model and 2021-2025. The wind and cold samples are small (88 games at 15+ mph).
- Stadium and crowd effects are inferred from proxies, since no crowd measurement exists.
- Late injuries and coaching decisions can invalidate a locked prediction.
- Betting lines carry information I can't fully separate from what is already in team stats.
- Early in a season the model has little recent form to work from, and accuracy against the baseline is weakest then.

---

## 8. Not built yet

- Component predictions (targets, carries, yards, touchdown probabilities). Only PPR points are published.
- The layered model (team environment, volume shares, efficiency, touchdowns) from section 6.
- The teammate-target effect from 5.9.
- A forecast weather source and a stadium table.
- The frozen-model control line on the Report card.
- Scheduled locking, which needs the AWS deployment.
- A running notes file for the experiment loop and an automated weekly recap. The ledger is the only record right now.

---

## 9. Reproducibility

`research/common.py`, `a_home_advantage.py`, `a4_team_home_edge.py`, `b_stability_and_touchdowns.py`, `d_context_ablation.py`, `e_models_and_components.py`, `f_weekly_learning.py`, `g_player_learning.py`, `h_error_anatomy.py`, `i_availability.py`, `j_population.py`, `k_train_wide_publish_narrow.py` and `l_calibration_population.py`. Results are in `research/results/*.json`. Run each with `.venv\Scripts\python research\<file>.py`.

## 10. Sources

- [Bleacher Report: home-field advantage](https://bleacherreport.com/articles/2656748-how-the-nfl-cheats-home-field-advantage)
- [The Ringer: NFL home-field advantage in 2020](https://www.theringer.com/2021/01/06/nfl/nfl-playoffs-home-field-advantage-covid-19-restrictions)
- [Davis and Krieger: how much of home-field advantage comes from fans](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3914238)
- [Farnell: an analysis of NFL penalties with and without crowds](https://journals.sagepub.com/doi/full/10.1177/15270025221148997)
- [Sports Insights: West Coast teams traveling east](https://www.sportsinsights.com/blog/is-there-still-a-disadvantage-for-nfl-west-coast-teams-traveling-east/)
- [SumerSports: sticky football stats](https://sumersports.com/the-zone/sticky-football-stats-predictive-nfl-metrics/)
- [ffopportunity (expected fantasy points)](https://ffopportunity.ffverse.com/)
- [Fantasy Points: expected touchdown regression](https://www.fantasypoints.com/nfl/articles/2023/xtd-touchdown-regression-candidates)
- [Fantasy Footballers: game script](https://www.thefantasyfootballers.com/articles/the-fantasy-football-mythbusters-flip-the-game-script/)
- [Sharp Football: implied team totals](https://www.sharpfootballanalysis.com/fantasy/nfl-implied-team-totals-tool/)
- [Going Deep: does defense-versus-position predict?](https://github.com/CommonFox/going-deep/issues/132)
- [Claremont thesis: temperature and wind](https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=1982&context=cmc_theses)
- [Bruin Sports Analytics: WR target distribution](https://www.bruinsportsanalytics.com/post/wr_target_dist)
- [Fantasy Football Analytics: which projections are most accurate](https://fantasyfootballanalytics.net/which-projections-are-most-accurate)
- [Hierarchical Bayesian fantasy projections](https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence/)
- [Poisson-exponential-Tweedie models for over-dispersed counts](https://arxiv.org/pdf/1908.08764)
- [Romano et al.: conformalized quantile regression](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf)
- [Walk-forward backtesting](https://machinelearningmastery.com/backtest-machine-learning-models-time-series-forecasting/)
- [LLMs on tabular data: a survey](https://arxiv.org/pdf/2402.17944)
- [Gradient boosting trees and LLMs for few-shot tabular data](https://arxiv.org/abs/2411.04324)
- [Hollmann et al.: CAAFE, context-aware automated feature engineering](https://arxiv.org/abs/2305.03403)
- [LLM-FE: LLMs as evolutionary optimizers for feature engineering](https://arxiv.org/pdf/2503.14434)
- [LLMs engineer too many simple features for tabular data](https://arxiv.org/pdf/2410.17787)
- [Claude Help Center: paid plans and the API](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console)
- [Claude Help Center: Claude Code with Pro or Max](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)

Several of these pages couldn't be fetched in full, so some claims rely on search-result summaries and say so where they appear. Every number I attribute to my own data was computed by the scripts in section 9.
