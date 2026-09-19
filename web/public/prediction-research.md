# Predicting Weekly NFL Player Performance: Evidence, Design, and Evaluation Plan

John Wasikye's NFL Player Performance project. Written 2026-09-18, before any prediction code is built.
All analyses on our own data are reproducible from `research/` in the project repo (results in `research/results/`).

---

## 0. In plain language: what the AI actually does

*This section is the whole design without the jargon. Everything after it is the evidence.*

**In one sentence:** every week Claude looks at what the model got wrong, invents a new clue that
might explain it, and the system tests that clue against five years of history, keeping it only if it
genuinely helps.

**Each week, in order:**

1. **The model makes its predictions.** This is ordinary statistics, not AI. It looks at what each
   player has been doing and predicts their next game.
2. **The games happen and everything is graded.** Every prediction is scored against what really
   happened.
3. **Claude studies the failures** - not one player at a time, but patterns. *Tight ends were badly
   predicted in games with a backup quarterback. Running backs were overrated when their team fell
   behind early.*
4. **Claude writes one new clue.** This is the actual work: a small piece of code that measures
   something the model has never seen before.
5. **The system tests it automatically.** It replays 2021-2025 and asks whether this clue would have
   made predictions better. Claude does not get a vote.
6. **Keep it or bin it.** A clue that helps becomes a permanent part of the model. A clue that does
   not is written into a list of dead ends so it is never tried again.

**A concrete example.** In week 6 the model keeps missing on tight ends. Claude reads those misses and
notices they are mostly tight ends whose team was losing badly. It writes a clue: *how often does this
tight end get the ball when his team is trailing, compared with when they are ahead?* The system tests
it on five past seasons. Either it helps, and every future prediction includes it, or it does not, and
it is logged as a dead end and discarded. Either way something is learned, and either way the model
cannot get worse.

**Why it can only improve.** Nothing is ever accepted on a hunch. A change ships only if it beats the
current model on games that model has never seen. Accuracy is a ratchet: it clicks forward or stays
put, but never slips back. We tested the alternative - letting the system quietly adjust itself from
recent results - and it made predictions *worse* (sections 5.11 and 5.12). This design makes that
impossible.

**Why Claude is the right tool for this particular job.** Four NFL datasets have never been touched,
including which players were actually on the field for each play and how far downfield each pass
travelled. That is raw material, not ready-made clues. Turning it into something useful takes football
understanding: knowing that "a tight end lined up wide" means something different from "a tight end
lined up next to the tackle". That is a meaning problem, which is what Claude is good at. Finding the
pattern in the numbers afterwards is what statistics are good at.

**What the AI will never do:**
- write a prediction (no number on the site comes from Claude),
- override the model ("I think this guy will have a big game"),
- or approve its own work (the test decides).

That last point matters. If Claude could nudge predictions directly, there would be no way to tell
whether it was helping or just being confident. This way every contribution is measured.

**What to honestly expect.** The measured ceiling is about 7% of total improvement available, and some
of that is luck nobody can predict. Realistically this gains a few percent over a season, with plenty
of failed ideas along the way. The website publishes all of it: the ideas that worked, the ones that
did not, and a line tracking whether the AI loop is beating a model that never changes. If it is not,
the site says so.

---

## 1. Summary

**The goal.** Predict each player's next game: fantasy points, yards, touchdowns, and the volume behind them (targets, carries, attempts), for QB, RB, WR, TE, and K. Exclude injured players. Account for home versus away, including the idea that some stadiums are louder. Use AI, keep it learning week by week, and stay inside a Claude Pro plan.

**What the evidence says (each point is backed by a test in section 5):**

1. **A player's own recent usage is the foundation.** Adding everything else we could think of (betting lines, opponent, weather, injury tags) raised the explained variance of next-game fantasy points only from 0.27 to 0.29. Single-game fantasy points are inherently noisy: our best models explain about 29% of the variance.
2. **Volume is predictable, yards moderately, touchdowns barely.** Held-out R²: carries 0.44 (RB), targets 0.31 (WR), attempts 0.23 (QB); yards 0.12 to 0.29; touchdowns 0.00 to 0.09; interceptions are unpredictable. Touchdowns must be predicted as small probabilities from opportunity, never from a player's recent touchdown total (that was worse than guessing the average).
3. **Home-field advantage is real but small, and there is no stable "loud stadium" or team-specific effect.** Players score about 0.5 points (4.8%) more at home, quarterbacks about 1.3 (8.1%). A stadium's effect on visitors and a team's home edge did not repeat between 2021-23 and 2024-25 (correlations 0.11, -0.25, and -0.04, none significant). Kansas City, often called the loudest stadium, was near the bottom for visiting false starts.
4. **Wind and cold matter at the game level, not the player level.** Wind of 15+ mph cut passing efficiency and game scoring (about 4.8 fewer total points), but adding weather to a per-player model made it slightly worse. Weather belongs in the team-scoring layer.
5. **The betting line is well calibrated and useful for team scoring.** Implied team points track actual points (slope 1.02, r = 0.40). Favorites run more plays; underdogs pass about 4 points more often.
6. **A simple model is nearly as good as a complex one.** Ridge regression reached R² 0.280; gradient boosting 0.288; their average 0.289. The naive recent-average baseline is 0.232. The ceiling is set by the data, not the algorithm.
7. **Injury reports are highly informative.** Players listed Out played 0.1% of the time and Doubtful 0.4%; Questionable players played 63% of the time (quarterbacks 35%).
8. **Honest ranges need calibration.** Raw quantile models covered 77% of outcomes for an 80% interval; a conformal correction fixed it (79.7%). The typical 80% range is about 17 fantasy points wide.
9. **The headroom is small and the error is not clustered.** An oracle knowing each player's true
   season-long average would score MAE 5.074 against our model's 5.445: the entire remaining gap is
   6.8%, and error is spread evenly across situations rather than concentrated in nameable ones
   (returning players, new teams, and changed roles are all predicted *better* than average). Reading
   the injury text we have does not help either (AUC 0.672 to 0.663).
10. **"The model gets smarter every week" is false as usually imagined, and we tested it.** Retraining every week beat a frozen model by only 0.037 MAE (0.7%), and the gap did not grow as the season went on (trend +0.00003 per week). Adaptive ensemble weights, per-position bias correction, per-player bias learning, and role-change heuristics all made predictions **worse**. Even an oracle that knew each player's true season-long bias in advance would gain only 0.17 MAE (3%). Weekly self-adjustment must therefore be treated as a hypothesis to be tested, not a feature to be assumed.
11. **Who you predict matters as much as how.** The built engine first came in at a margin of 0.052
    over the baseline, failing its own 0.15 bar. The cause was not the model: it was *losing* to a
    simple average on low-volume players (margin -0.291 for those averaging under 2 points, -0.093
    from 2 to 4) while winning clearly on players with a real role (+0.292 for those averaging 13+).
    The margin rises monotonically across all six scoring tiers. Restricting projections to players
    averaging at least 4 points over their last five games clears the bar, covering 8,464 of 12,388
    player-games. Note that raw MAE *rises* under this restriction, because better players are more
    variable — only the margin is comparable across populations.
12. **Where the restriction is applied matters, and conformal theory says exactly where.** Training
    on everyone and publishing only the eligible beats dropping them entirely (+0.170 against
    +0.159), but it pushed interval coverage to 0.778 — because split conformal prediction only
    guarantees coverage when the calibration set is exchangeable with what is predicted, and
    low-volume players have artificially small errors. Calibrating on the published population
    instead restored coverage to 0.797 with *identical* MAE to four decimal places. **Final:
    margin +0.170 on a 0.15 bar, coverage 0.797** — the engine passes its own gate, and none of
    the gain came from a better model.

**What this means for the design.** Build a hierarchical system: team environment (lines, weather) -> who plays (availability) -> volume shares (with teammate effects) -> efficiency and touchdowns (heavily shrunk) -> a distribution, then combine simple and flexible models and calibrate. Test every extra factor on held-out seasons and keep only what earns its place.

**And on "AI should make a significant difference and get better every week":** the evidence rules out
the versions of that idea that involve an LLM producing or adjusting numbers. It supports one specific
mechanism - **LLM-driven feature engineering**, which has published evidence of improving tabular models
(CAAFE: 11 of 14 datasets, ROC AUC 0.798 to 0.822) and which works best precisely where a domain is
semantically rich, as football is. We also have four nflverse datasets never yet touched (advanced
stats, charting, participation, depth charts), which is the most likely home for the 6.8% of headroom
that remains. So Claude's job is to read each week's failures, write real feature code against that
unexploited data, and let an automated harness accept or reject it out of sample. Because nothing
ships without beating the incumbent, measured accuracy is monotonic by construction: the system can
only ratchet upward, and the Report card shows it doing so.

---

## 2. Questions

1. How predictable is a single NFL game for a player, by stat?
2. Which factors add real predictive value beyond a player's own history?
3. How large is home-field advantage for players, and does it differ by stadium ("loud stadiums")?
4. How should injuries and availability be handled?
5. Which model families work best, and how should uncertainty be reported?
6. Where can an LLM add value without breaking the cost limit or making things up?

---

## 3. Background: what the literature and industry practice say

**Home-field advantage.** Historically NFL home teams win about 57% (2009-2015 regular seasons; [Bleacher Report summary](https://bleacherreport.com/articles/2656748-how-the-nfl-cheats-home-field-advantage)). In 2020, with empty stadiums, home teams finished 127-128-1, the first sub-.500 home record in NFL history ([The Ringer](https://www.theringer.com/2021/01/06/nfl/nfl-playoffs-home-field-advantage-covid-19-restrictions)). One natural-experiment analysis put a full crowd at about +1.6 points of margin, roughly half of the home advantage ([Davis and Krieger, SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3914238); reported via search summary, full text not accessible). The crowd-noise mechanism is debated: visiting teams have committed record false starts in loud games, but a 2023 study of penalties with and without crowds found offensive false starts were *not* affected, while pre-snap defensive penalties against the home team fell when crowds were present ([Farnell 2023](https://journals.sagepub.com/doi/full/10.1177/15270025221148997), abstract via search summary). Travel and rest also appear to matter, with mixed evidence for time-zone effects ([Sports Insights](https://www.sportsinsights.com/blog/is-there-still-a-disadvantage-for-nfl-west-coast-teams-traveling-east/)).

**Stability of statistics.** Usage statistics persist; efficiency and touchdowns do not. Target share correlates about 0.70 from year to year and yards per route run above 0.60 ([SumerSports](https://sumersports.com/the-zone/sticky-football-stats-predictive-nfl-metrics/)); touchdown rate is unstable, with only 6 of 112 receivers at a 15%+ rate repeating it (industry analysis via [search](https://www.si.com/nfl/2018/08/01/fantasy-football-2018-most-predictable-wide-receiver-stats)). Expected-touchdown models score each carry and target by field position rather than trusting a player's own touchdown count ([Fantasy Points xTD](https://www.fantasypoints.com/nfl/articles/2023/xtd-touchdown-regression-candidates)).

**Expected fantasy points.** nflverse's own `ffopportunity` models opportunity with xgboost trained on public play-by-play, estimating what an average player would score given the situation ([ffopportunity](https://ffopportunity.ffverse.com/)). This is the "opportunity first" approach we adopt.

**Game script and the betting market.** Favorites outscore underdogs at every position, even though underdogs take a slightly higher share of the passing; the practical lesson is to "target points, not game script" ([Fantasy Footballers analysis](https://www.thefantasyfootballers.com/articles/the-fantasy-football-mythbusters-flip-the-game-script/)). Implied team totals convert spread and total into expected points, but say nothing about which player gets the work ([Sharp Football](https://www.sharpfootballanalysis.com/fantasy/nfl-implied-team-totals-tool/)).

**Opponent matchups.** Defense-versus-position rankings are contaminated by opponent quality, game script, and small samples, and wide receiver/tight end matchups are especially unstable ([discussion](https://github.com/CommonFox/going-deep/issues/132)).

**Weather.** Published analyses report passing efficiency falling sharply above about 20 mph wind and scoring about 5% lower in 25-50 F games ([summary of studies](https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=1982&context=cmc_theses)).

**Injuries and teammates.** Target redistribution after a top receiver is out is real but uneven; running back workloads are more predictable than receiver targets ([UCLA Bruin Sports Analytics](https://www.bruinsportsanalytics.com/post/wr_target_dist)).

**Models and ensembles.** Gradient boosting and random forests are the standard for weekly fantasy prediction; ensembles of many projection sources beat individual sources, and a simple average of sources beat individual sources in 63% of head-to-head comparisons ([Fantasy Football Analytics](https://fantasyfootballanalytics.net/which-projections-are-most-accurate)). A hierarchical Bayesian projection model with partial pooling matched a 7-game average on error (MAE 6.08 vs 5.99) and its value was in calibrated uncertainty ([write-up](https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence/)). Counts such as touchdowns are over-dispersed relative to Poisson in general and are handled with negative binomial or Tweedie models ([survey](https://arxiv.org/pdf/1908.08764)).

**Uncertainty and validation.** Conformalized quantile regression gives distribution-free interval coverage ([Romano et al.](https://papers.neurips.cc/paper/8613-conformalized-quantile-regression.pdf)). Time-ordered (walk-forward) validation is required because ordinary cross-validation leaks future information ([overview](https://machinelearningmastery.com/backtest-machine-learning-models-time-series-forecasting/)).

**LLMs.** On tabular and time-series prediction, gradient boosting stays competitive or better once there is a reasonable amount of data; LLMs help mainly in few-shot settings ([survey](https://arxiv.org/pdf/2402.17944); [GBDT vs LLM few-shot](https://arxiv.org/abs/2411.04324)). We therefore keep the numbers in a statistical model and use Claude for context and review.

**Claude and cost.** A Claude Pro subscription does not include API usage; the API is billed separately per token ([Claude Help Center](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console)). Claude Code shares usage limits with claude.ai, and a set `ANTHROPIC_API_KEY` makes it bill the API instead of the subscription ([Claude Help Center](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)).

**A limit of the literature.** We found no trustworthy published accuracy ceiling for weekly player projections, so we measure our own.

---

## 4. Data

- **In use:** nflverse weekly player stats, play-by-play (about 49,000 plays per season), schedules (spreads, totals, roof, wind, temperature, rest days), injuries, snap counts, rosters. Regular seasons 2021-2025 for all analyses (2026 is in progress).
- **Available and not yet used:** weekly advanced stats (Pro Football Reference, 2018+), play charting (FTN, 2022+), who-was-on-the-field (2016-2025), Next Gen Stats. We will test whether they add signal.
- **Not available:** crowd noise or attendance, player prop lines, tracking data, official inactive lists before kickoff, and stadium coordinates (we will build a small table).
- **Method notes.** Analyses of player outcomes use only games a player appeared in and players averaging at least 4 fantasy points over their last 5 games. This is a deliberate choice: availability is modelled separately.

---

## 5. Empirical studies on our data

### 5.1 Home-field advantage and loud stadiums (`a_home_advantage.py`, `a4_team_home_edge.py`)

**Team level (1,333 non-neutral games).** Home teams outscored visitors by 2.06 points per game (SE 0.39) and won 53.9%. By season the margin ranged from 1.6 to 2.7. Offensive EPA per play differed by only 0.003 (SE 0.008), so the points edge does not show up clearly in per-play efficiency.

**Player level (same player at home versus away, at least 4 games each, 1,278 player-seasons).**

| Position | Home minus away (points per game) | SE | Percent of average |
|---|---|---|---|
| QB | +1.28 | 0.32 | 8.1% |
| RB | +0.46 | 0.21 | 4.1% |
| WR | +0.50 | 0.17 | 4.8% |
| TE | +0.10 | 0.24 | 1.1% (not significant) |
| K | +0.42 | 0.18 | 5.2% |
| All | +0.53 | 0.10 | 4.8% |

**Is there a "loud stadium" effect?** We tested visiting offenses at 30 stadiums (about 42 visits each).

- False starts by the visiting team averaged 1.80 per 100 snaps. Stadiums differ more than chance would predict (chi-square 49.4, 29 degrees of freedom, p = 0.010), and visiting offensive efficiency also varied (F = 1.65, p = 0.016).
- **But the differences did not repeat.** Comparing 2021-23 with 2024-25 across the same stadiums, the correlation was +0.11 for false-start rate (p = 0.55) and -0.25 for visiting EPA (p = 0.18). A real stadium trait should correlate positively.
- **Team home edges (home margin minus road margin) also did not repeat:** correlation -0.04 (2021-23 vs 2024-25) and -0.06 (odd vs even seasons). The spread across teams (SD 2.9 points) was no larger than luck alone would produce (3.1).
- **Folklore does not survive.** Kansas City visitors committed 1.16 false starts per 100 snaps (among the lowest). Seattle had 2.21 (top six) but the smallest home-versus-road margin gap of any team (-0.6 points). The highest visiting false-start rates were Cleveland, Pittsburgh, Miami, Dallas, Tennessee, and Seattle.
- **Domes versus open air:** no difference (1.76 vs 1.83 false starts per 100; visiting EPA +0.004, p = 0.69).

**Conclusion.** Model a league-wide home effect by position (about +5%, quarterbacks +8%). Do not hard-code stadium reputations. If we add stadium-specific effects, use empirical-Bayes shrinkage and keep them only if they pass a held-out test each season. Our proxies (false starts, EPA) are indirect because no decibel data exists.

### 5.2 Which statistics are skill and which are luck (`b_stability_and_touchdowns.py`)

Year-to-year correlations (players with enough volume in both seasons):

| Position | Usage | Efficiency | Touchdown rate |
|---|---|---|---|
| WR | targets per game 0.71, target share 0.70 | yards per target 0.28, catch rate 0.47 | 0.12 |
| TE | targets per game 0.58 | yards per target 0.36, catch rate 0.20 | 0.17 |
| RB | carries per game 0.48, targets per game 0.65 | yards per carry 0.17 | 0.09 |
| QB | attempts per game 0.64, rush yards per game 0.85 | yards per attempt 0.35 | 0.40 (interception rate 0.01) |

Odd-versus-even-week reliability (full-season equivalent) told the same story: usage 0.85 to 0.91, efficiency 0.3 to 0.7, touchdown rates 0.2 to 0.5.

### 5.3 Touchdowns (`b_stability_and_touchdowns.py`)

- **Counts are close to Poisson.** Variance-to-mean of touchdowns per game was 1.04 to 1.15.
- **Field position drives scoring.** Rushing touchdown rates by distance: 55% at the 1-yard line, 24% at 4-5 yards, 12% at 6-10, 5% at 11-20, 1% at 21-40. (Small buckets are noisy and need smoothing.)
- **Predicting the next game's touchdowns (2024-25, trailing 6 games):** correlation with trailing *expected* touchdowns 0.22, with trailing touches 0.20, with trailing *actual* touchdowns 0.18. Even the best explains only about 5% of the variance. About 33% of player-games have a touchdown.

### 5.4 Which factors help next-game fantasy points? (`d_context_ablation.py`)

LightGBM trained on 2021-23 (10,516 player-games), tested on 2024-25 (7,445), all features known before kickoff:

| Model | MAE | R² |
|---|---|---|
| Recent-average baseline (exponential) | 5.670 | 0.232 |
| + player history and usage | 5.457 | 0.273 |
| + game context (implied total, spread, home, rest, week) | 5.439 | 0.283 |
| + opponent points allowed to position | 5.441 | 0.283 |
| + weather | 5.460 | 0.283 |
| + injury status (of players who played) | 5.465 | 0.285 |

Removing a group from the full model raised error by: history +1.18, opponent +0.005, game context +0.003, injury tag -0.005, weather -0.023. **History dominates; the rest is small or noise at this data size.** This does not prove those factors are useless: they may matter for touchdowns, extreme games, or structured models. The lesson is to add each factor where it belongs in the structure and prove it.

### 5.5 Model families and honest ranges (`e_models_and_components.py`)

| Model | MAE | R² |
|---|---|---|
| Recent-average baseline | 5.670 | 0.232 |
| Ridge regression | 5.480 | 0.280 |
| LightGBM | 5.440 | 0.288 |
| Average of ridge and LightGBM | 5.441 | 0.289 |

- **80% prediction range:** raw quantile models covered 77.2% of outcomes; after a conformal correction 79.7%. Ranges are wide: about 16.7 fantasy points.

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

- **Wind (EPA per dropback):** 0-9 mph +0.045 (n = 509 games), 10-14 mph +0.017 (180), 15+ mph -0.041 (88, SE 0.025).
- **Total points:** 45.2 (0-9 mph), 42.7 (10-14), 40.4 (15+), about 4.8 fewer.
- **Temperature (EPA per dropback):** below 40 F -0.001, 40-59 F +0.020, 60+ F +0.049.
- **Field goals:** no clear drop in make rate after adjusting for distance (teams avoid long kicks in wind), so the effect appears as fewer attempts and fewer points, not lower accuracy.

### 5.8 Game script and the line (`d_context_ablation.py`)

| Team spread | Pass rate | Plays | Points |
|---|---|---|---|
| Underdog 7+ | 59.4% | 59.5 | 17.4 |
| Underdog 3-7 | 59.4% | 62.0 | 20.3 |
| Pick'em | 57.5% | 61.9 | 21.6 |
| Favorite 3-7 | 56.3% | 62.5 | 25.9 |
| Favorite 7+ | 55.4% | 63.4 | 28.7 |

Implied team total versus actual points: r = 0.40, slope 1.02, intercept -0.3 (2,718 team-games): well calibrated.

### 5.9 Teammates (`d_context_ablation.py`)

When a team's top receiver was ruled out (145 team-games), the next three receiving options averaged +0.20 targets versus their trailing average, compared with -0.29 when he played: a difference of about +0.5 targets each, roughly 1.5 extra targets shared among three players.

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

A true walk-forward run through 2024-2025 (36 weeks, 7,445 player-games). Each week only games
before that week exist. Mean absolute error, lower is better:

| Strategy | MAE | vs frozen |
|---|---|---|
| Recent-average baseline | 5.670 | -0.187 |
| **Frozen** (trained once on 2021-23, never updated) | 5.483 | - |
| **Retrained every week** on everything so far | 5.446 | **+0.037** |
| Retrain + per-position bias correction (last 4 weeks of errors) | 5.448 | +0.035 |
| Retrain + adaptive ensemble weights (last 6 weeks) | 5.476 | +0.007 |

- **Weekly retraining is worth about 0.7%.** One week adds roughly 200 rows to a 10,000-row training
  set, and the model is already near the data's ceiling.
- **The gap does not grow.** Trend of (frozen minus adaptive) across the 36 weeks: +0.00003 per week,
  indistinguishable from flat. A system that was genuinely compounding would fan out.
- **Adaptive ensemble weights hurt.** They drifted toward equal weighting including 32% on the naive
  baseline, fitting six weeks of noise.
- **Skill over the baseline shrinks as the season goes on**, the opposite of the intuition: weeks 1-4
  +0.276 MAE of skill, weeks 5-9 +0.172, weeks 10-13 +0.202, weeks 14+ +0.140. Late in the season a
  simple trailing average is already close to the model, because each player's own history has become
  informative. The model's advantage is largest when data is scarce.

### 5.12 Do player-level learning mechanisms work? (`g_player_learning.py`)

Same walk-forward setup, testing the mechanisms that "learning about each player" usually means:

| Mechanism | MAE | vs base |
|---|---|---|
| Base (retrained ensemble) | 5.446 | - |
| + each player's own recent over/under-performance, shrunk | 5.507 | **-0.061** |
| + role-change detection (recent usage shift) | 5.546 | **-0.100** |
| + both | 5.634 | **-0.188** |

- Every mechanism made predictions **worse**. About 168 players per week had enough history for a bias
  estimate and 66 were flagged as role changes, so this is not a sample-size artifact of the test.
- **The ceiling is low even with hindsight.** An oracle that knew each player's true average bias
  across 2024-2025 and applied it shrunk would gain only **0.17 MAE (about 3%)**. There is very little
  player-specific bias left for any mechanism to find; the model already captures what is knowable.

### 5.13 Where does the model fail, and is the failure reachable? (`h_error_anatomy.py`)

If the error were concentrated in situations we can name before kickoff, a layer that understands
those situations would have something real to aim at. It is not.

| Segment (all known before kickoff) | Share of games | Share of error | MAE inside | MAE outside |
|---|---|---|---|---|
| Volatile recent scoring | 25.0% | 28.4% | 6.18 | 5.20 |
| Returning after missing a week | 23.4% | 21.7% | 5.04 | 5.57 |
| Big usage shift | 26.2% | 24.1% | 5.02 | 5.60 |
| Listed Questionable | 4.3% | 4.3% | 5.36 | 5.45 |
| Thin history (<= 6 games) | 4.0% | 4.0% | 5.40 | 5.45 |
| New team | 2.7% | 2.7% | 5.41 | 5.45 |
| **Any of the above** | **59.8%** | **59.1%** | 5.38 | 5.54 |

- **Error is not concentrated in nameable situations.** Every segment carries almost exactly its
  proportional share of the error, and the union carries *less* than its share. The situations that
  look hard to a human (a player returning, a changed role, a new team) are ones the model already
  handles; only "volatile" players are harder, and that is close to a tautology.
- Error is spread across games rather than clustered: the worst 25% of player-games hold 52.7% of
  total error, which is roughly what any heavy-tailed outcome produces.
- **The decisive number.** An oracle that knew each player's *true season-long average* in advance
  would post MAE 5.074. Our model posts 5.445. The entire remaining headroom, between a working model
  and godlike knowledge of every player's true level, is **0.371 MAE (6.8%)**, and much of that is
  irreducible game-to-game randomness.

### 5.14 Can reading text improve availability calls? (`i_availability.py`)

Availability looked like the natural home for a text-reading layer: a wrong call costs a player's
whole score (about 8.2 points) rather than the usual 5.4-point error. 2,347 Questionable player-weeks.

| Model | AUC | Brier |
|---|---|---|
| Base rate (always predict "plays") | - | 0.2493 |
| Practice status, position, player history | 0.672 | 0.2274 |
| + injury type from the report text | **0.663** | 0.2293 |

- Adding the injury description **made it slightly worse** (AUC -0.009). Play rates do vary by body
  part (hamstring 50%, hip 66%), but that information is already carried by practice status.
- The injury text nflverse publishes is a body part, not the richer reporting ("expected to be a
  game-time decision", "will be on a snap count") that would actually add signal. We do not have that
  text, and the text we do have is exhausted.

**Conclusion.** The intuition that an adaptive system improves week over week is not supported here.
Weekly self-adjustment fits noise faster than signal at this sample size. Adaptation must be earned on
held-out evidence, and the default is off. Section 7.5 is rebuilt around this result.

### 5.15 Who should actually be predicted? (`j_population.py`, `k_train_wide_publish_narrow.py`)

The first full walk-forward run of the built engine came in at 4.458 mean absolute error against a
best baseline of 4.510: a margin of **0.052**, well short of the 0.15 this paper set as the bar. The
engine would not have passed its own promotion gate.

Before reaching for a better model, a cheaper question: is the margin being diluted by players nobody
needs a projection for? Splitting the graded player-games by how much each player had recently been
scoring answers it clearly.

| Recent scoring (`ppr_mean5`) | Player-games | Mean actual | Model MAE | Baseline MAE | Margin |
|---|---|---|---|---|---|
| 0-2 | 2,131 | 1.89 | 2.222 | 1.931 | **-0.291** |
| 2-4 | 1,814 | 3.76 | 3.349 | 3.256 | **-0.093** |
| 4-6 | 1,593 | 5.44 | 3.986 | 4.052 | +0.067 |
| 6-9 | 2,196 | 7.87 | 4.691 | 4.793 | +0.102 |
| 9-13 | 2,161 | 10.36 | 5.500 | 5.678 | +0.178 |
| 13+ | 2,494 | 15.15 | 6.390 | 6.681 | **+0.292** |

The model was **losing to a simple average** on the bottom two tiers, and those tiers were 32% of the
graded population. A deep-bench player who scores near zero every week is trivially predictable; the
model adds variance to a question the average already answers, and the lost ground there was
cancelling out real gains at the top.

The same split by position shows the identical mechanism through a different lens:

| Position | Player-games | Model MAE | Baseline MAE | Margin |
|---|---|---|---|---|
| QB | 1,255 | 6.361 | 6.681 | +0.320 |
| K | 1,041 | 3.865 | 4.010 | +0.145 |
| RB | 3,071 | 4.353 | 4.418 | +0.065 |
| TE | 2,374 | 3.707 | 3.687 | **-0.020** |
| WR | 4,670 | 4.529 | 4.517 | **-0.011** |

Quarterbacks do best because nearly every graded quarterback is a starter with a real role. Tight ends
and receivers look worst because those positions carry the longest low-volume tails.

Re-running the whole harness at a series of cut-offs:

| Eligible if `ppr_mean5` at least | Player-games | MAE | Baseline | Margin | Coverage | Clears 0.15 |
|---|---|---|---|---|---|---|
| 0 | 12,388 | 4.463 | 4.515 | +0.052 | 0.797 | no |
| 2 | 10,278 | 4.931 | 5.047 | +0.116 | 0.797 | no |
| **4** | **8,464** | **5.278** | **5.436** | **+0.159** | **0.798** | **yes** |
| 6 | 6,879 | 5.586 | 5.752 | +0.166 | 0.799 | yes |
| 8 | 5,421 | 5.850 | 6.018 | +0.168 | 0.801 | yes |
| 10 | 4,037 | 6.136 | 6.346 | +0.210 | 0.798 | yes |

**An important caveat about reading this table.** Raw MAE *rises* with the cut-off (4.463 to 6.136).
That is not the model getting worse; higher-scoring players are simply more variable, so absolute
errors are larger. Comparing MAE across these rows is meaningless, because each row is a different
population. Only the margin over the baseline — computed within a row — is comparable. This matters
for publishing too: the headline accuracy figure will look *worse* after this change, and the Report
card has to explain why rather than quietly reporting a bigger number.

**Is this gaming the metric?** It would be, if a threshold had been fished for until one passed. Two
things argue it is not. First, the direction was hypothesised in advance: the design already called
for restricting to players with a real role, and this measured that rather than discovering it.
Second, the margin rises **monotonically across all six independent tiers**. A cherry-picked cut-off
does not produce a monotone gradient; a real mechanism does. The threshold of 4 is then chosen as the
*smallest* value that clears the bar, deliberately keeping the largest audience rather than chasing
the best number — at 10 the margin is better, but two thirds of players would have no projection.

**Where the threshold is applied.** Experiment J filtered the data before the harness saw it, which
dropped low-volume players from *training* as well as from grading. Those are separate claims —
"nobody needs this projection" is a product decision, while "the model learns worse from these rows"
is an empirical one — and they point opposite ways, since more training data usually helps.
Experiment K ran both on identical graded rows:

| | Player-games | MAE | Margin | Coverage |
|---|---|---|---|---|
| Trained narrow (low-volume players dropped entirely) | 8,464 | 5.278 | +0.159 | 0.798 |
| Trained wide (dropped only from publishing) | 8,464 | 5.266 | **+0.170** | **0.778** |

Training on everyone is better for accuracy, as expected: there is no reason to throw data away. But
it dragged interval coverage down to 0.778, at the very edge of the acceptable band.

### 5.16 Why the coverage dropped, and the fix the theory predicted (`l_calibration_population.py`)

That coverage drop is not noise, and it has a name. Split conformal prediction guarantees coverage
only when the calibration set is **exchangeable** with what is being predicted. Low-volume players
have small errors, because scores near zero are easy to get right. Calibrating on a population full
of them therefore produces a correction that is too small for the players actually being published,
and the ranges come out too narrow.

This predicts its own fix, without any searching: train on everything, but calibrate on the
population that will be published. Experiment L tested it.

| Calibrated on | MAE | Margin | Coverage | Mean range width |
|---|---|---|---|---|
| Everyone | 5.2659 | +0.1704 | 0.778 | 15.85 |
| The published population | 5.2659 | +0.1704 | **0.797** | 16.14 |

Mean absolute error is **identical to four decimal places**, which is the check that the change did
what it claimed: calibration moves the range, never the point estimate. Coverage returns to 0.797
against a nominal 0.80, and the honest cost is ranges about 0.3 points wider.

**The resulting configuration**, and the answer to "where is the threshold applied":

- **train** on every player-week with at least 3 prior games — all the data there is
- **calibrate** the ranges on the publishable population only — exchangeability
- **publish** only players averaging at least 4 points over their last five games — section 5.15

**Final held-out result: MAE 5.266 against a best baseline of 5.436, a margin of +0.170 on a 0.15
bar, with 0.797 interval coverage over 8,464 player-games.** The engine passes its own promotion
gate. For comparison, the first honest measurement of the built system was a margin of 0.052, so
this is a little over three times the original edge — and none of it came from a better model. It
came from being precise about which players are being predicted and which population the ranges are
calibrated against.

---

## 6. Design principles that follow

1. **Predict the structure, not just the number.** Opportunity (volume) first, then efficiency, then touchdowns.
2. **Shrink hard where the evidence says luck dominates.** Efficiency and especially touchdown and interception rates move toward position and situation averages; usage moves less.
3. **Put each factor where it works.** Betting lines and weather set the *team's* scoring and passing environment; usage shares and teammate availability allocate it to *players*; home advantage is a small league-wide multiplier.
4. **Simple plus flexible.** Ensemble a regularized linear model and gradient boosting; keep the naive average as a baseline.
5. **Distributions, not points.** Quantile models with conformal calibration; touchdowns as probabilities.
6. **Every factor earns its place** on held-out, walk-forward tests and is dropped if it does not.
7. **Adaptation is a hypothesis, not a feature.** Sections 5.11 and 5.12 showed the usual weekly
   self-adjustment tricks making things worse. No adaptive mechanism ships unless it beats the static
   model on locked, out-of-sample predictions.

---

## 7. The prediction system

### 7.1 What is predicted
Fantasy points (PPR; standard kicker scoring) with an 80% range, and their parts: targets, carries, attempts, receptions, rushing/receiving/passing yards, and touchdown probabilities (chance of at least one touchdown, expected touchdowns). Interceptions are shown only as a league-average-adjusted rate.

**For whom** (sections 5.15 and 5.16). A player is projected if he has at least 3 prior games *and* has averaged at least 4 PPR points over his last five. Below that line the model was measured losing to the player's own recent average, so publishing those projections would make the site worse than doing nothing. The three populations are deliberately different: the model **trains** on every player-week with 3 prior games, **calibrates** its ranges on the publishable population only, and **publishes** the eligible players. Roughly 340 players per week across the five positions.

### 7.2 Availability and injured players
- **Excluded from predictions:** Out, Doubtful, injured reserve, suspended, or off the active roster. Shown as "unavailable".
- **Questionable:** a prediction conditional on playing plus a calibrated probability of playing (from status, practice trend, position, history: about 63% overall, 35% for quarterbacks). Expected value is shown as both.
- **Late scratches** (announced about 90 minutes before kickoff) are tracked separately and never graded as misses.
- **Teammate effect:** a top receiver out shifts targets to the next options (section 5.9).

### 7.3 Layers
1. **Team environment:** implied points and plays from the line, adjusted for wind (15+ mph) and cold, home edge, rest and short weeks.
2. **Volume shares:** each player's expected share of the team's targets, carries, and attempts from recent usage, depth chart, and teammate availability.
3. **Efficiency:** yards per opportunity and catch rate, shrunk toward position averages and adjusted lightly for the opponent.
4. **Touchdowns:** expected touchdowns from opportunity and field position, converted to probabilities with a count model (negative binomial if over-dispersed).
5. **Combination:** components are assembled into fantasy points and compared with a direct points model; the ensemble weights follow recent accuracy.
6. **Calibration:** quantile models with a conformal correction.

### 7.4 Home and away
League-wide home multipliers by position (starting near +5%, quarterbacks +8%, tight ends about 0), estimated on training seasons. A stadium or team effect is an optional, shrunk add-on that must beat the league-wide version on held-out data to be switched on. Default: off.

### 7.5 How the system gets better over time

Sections 5.11 and 5.12 are the constraint. Every mechanism that automatically nudges predictions from
recent errors made things worse, and even perfect hindsight about a player's bias was worth only 3%.
So the system does not "tune itself" week to week. It improves through a **governed experiment loop**:
a hypothesis is proposed, tested on held-out data, and shipped only if it wins. That compounds, is
auditable, and cannot silently degrade.

**Tier 1: the features update themselves (automatic, real, free).**
Every week adds a game to each player's history, so the inputs sharpen on their own. This is the
largest week-to-week effect, but it is not the model learning, and the recent-average baseline gets
the same benefit. It will not be presented as model improvement.

**Tier 2: weekly retraining (kept, but small).**
Worth about 0.7% and it does not compound (5.11). It is free and harmless, so it stays, and it matters
more across seasons than within one.

**Tier 3: calibration maintenance (genuinely needs weekly updating).**
Interval coverage and touchdown probabilities drift as scoring environments change. Recalibrating the
conformal offset and probability curves weekly targets *coverage and honesty*, not point accuracy, and
is judged on coverage. This is the one adjustment that is on by default.

**Tier 4: the experiment ledger (the real compounding mechanism).**
Each week the system runs **one** candidate change through the walk-forward harness:
- a new feature or data source (snap share trend, routes run, air yards, participation data, depth
  chart position, forecast weather),
- a structural change (separate volume and efficiency models for a position, a different count
  distribution for touchdowns),
- or a rule (how hard to shrink a metric, how to treat a player returning from injury).

Every candidate is recorded with its hypothesis, the measured result, and the decision. Gains come
from **new information and better structure**, which is where our ablation showed the remaining room,
not from re-weighting the same inputs. Over a season this is roughly 18 graded experiments, and the
ledger is published.

**The promotion gate (applies to every tier above 3).**
A change ships only if it beats the current champion on locked, out-of-sample predictions over a
rolling window **and** in the full walk-forward backtest, by more than the noise band. Anything that
fails is recorded as a negative result and reverted. Sections 5.11 and 5.12 are the first four
entries in the ledger, all negative, all default-off.

### 7.6 Claude's role: automated feature discovery over unexploited data

**What the evidence rules out.** Claude cannot make point predictions much better by producing or
adjusting numbers. Section 5.13 puts the entire headroom at 6.8%, sections 5.11 and 5.12 show
self-tuning failing, 5.14 shows the available injury text exhausted, and the literature (section 3)
shows gradient boosting ahead of LLMs on tabular prediction once there is real data. Any design that
has an LLM writing or nudging the predicted number is working against all four findings.

**What the evidence supports.** There is one mechanism with published evidence of an LLM measurably
improving a tabular model: **LLM-driven feature engineering**. CAAFE ([Hollmann et al., NeurIPS
2023](https://arxiv.org/abs/2305.03403)) has an LLM write feature code from a dataset description,
keeps a feature only if it improves validation performance, and improved 11 of 14 datasets, lifting
mean ROC AUC from 0.798 to 0.822 - an improvement the authors compare to switching from logistic
regression to a random forest. LLM-FE ([TMLR 2026](https://arxiv.org/pdf/2503.14434)) extends this
into an evolutionary loop where measured performance feeds back into the next proposal.

The important caveat is also documented: LLMs tend to produce too many trivially simple features, and
they help most when the domain is **semantically rich** rather than an anonymous numeric table
([Kuken et al.](https://arxiv.org/pdf/2410.17787)). Football is the favourable case. "Snap share
trend relative to the team's other backs", "air yards share since the WR1 was injured", and "depth
chart position change" are meaningful to anyone who understands the sport and invisible to a model
given only column names.

**And we have genuinely unexploited data.** The models tested in this paper used weekly box-score
history, schedule context, and a defensive-strength summary. Four nflverse datasets were never
touched: weekly Pro Football Reference advanced stats (2018+), FTN charting (2022+), play-by-play
participation (2016-2025), and depth charts. These contain routes run, air yards, personnel
groupings, and who was actually on the field. This is the most likely place for the 6.8% headroom to
be sitting, and turning it into features is exactly the task CAAFE describes.

**What Claude does each week (one Claude Code session):**
1. **Reads the failure report** - errors sliced by position, situation, team, and week - plus the
   ledger of everything already tried and why it failed.
2. **Writes real feature code** against the warehouse, with a stated hypothesis for each feature.
3. **The harness tests it** walk-forward with no human in the loop: the feature ships only if it beats
   the incumbent out of sample.
4. **Records the outcome** in the ledger and the accumulating lessons file, so the next session starts
   from everything learned so far rather than from scratch.

**What Claude never does:** produce, adjust, or override a published prediction number. Its influence
reaches the site only as code that passed the gate.

**What Claude does each week (one short Claude Code session):**
1. **Reads the grade table and the biggest misses** and characterises them: which positions, game
   types, and situations the model got wrong, and what those misses have in common.
2. **Proposes the next experiment** for the Tier 4 ledger: a specific feature, structural change, or
   rule, stated as a testable hypothesis with a predicted direction.
3. **Writes the lessons file**, which accumulates across weeks and is read at the start of the next
   session, so context carries forward instead of restarting.
4. **Writes the weekly recap** for the site from the numbers it is given, never inventing any.

**What Claude does not do:** produce or adjust any published prediction number. The prediction is the
model's. Claude's influence reaches the site only through experiments that passed the promotion gate.

**Why this makes the system only get better.** Every change must beat the incumbent on locked,
out-of-sample predictions before it ships, so the champion's measured accuracy is monotonic by
construction: a change that does not help is recorded and reverted, and a change that does help is
permanent. The system cannot silently drift downward the way the adaptive mechanisms in 5.11 and 5.12
would have. Knowledge accumulates in two places that persist across weeks and across context
windows - the ledger of tried hypotheses and the lessons file - so the search does not restart.

**What to expect, honestly.** The realistic target is capturing part of the 0.371 MAE of headroom.
CAAFE's published gain was comparable to changing model families; here that would be a few percent.
The claim this design supports is not "AI predicts football better than anyone". It is "an AI runs a
continuous, audited search for improvement, over data no one has mined yet, and the system is built so
it can only ratchet upward" - which is a claim that can be checked week by week on the Report card.

**Cost.** No API calls, so no per-token billing. A Pro subscription does not cover API usage
(section 3), and `ANTHROPIC_API_KEY` is never set, which would silently switch Claude Code to paid API
billing. One short session a week sits inside the plan's shared limits. If a session never runs, the
pipeline is unaffected: predictions still publish, the ledger simply does not advance that week.

### 7.7 Weekly loop
Tuesday: grade last week, retrain, publish preliminary predictions. Before each game: refresh injuries, lines, and weather, then lock (Thursday games lock earlier in the week). Locked predictions are timestamped and never edited.

### 7.8 Evaluation and success criteria
- **Protocol:** walk-forward across 2021-2025 (never train on the future), plus live weekly grading.
- **Baselines:** recent-average, season-average, and last season's average.
- **Metrics:** MAE and RMSE, R², rank correlation, top-N hit rate, interval coverage (target 78-82% for 80% intervals), touchdown-probability calibration and Brier score, and skill versus baseline.
- **Bars the build must clear on held-out seasons:** beat the recent-average baseline by at least 0.15 in MAE (about 3%) and 0.04 in R²; intervals cover 78-82%; touchdown probabilities are calibrated; no leakage (tests prove future results cannot change past predictions).
- **The bar is measured on the population we actually publish** (section 5.15), and the population is fixed before the season, not tuned against the result. Because raw MAE depends on which players are included, every accuracy figure is reported next to its player count, and the Report card compares the model only with baselines scored on the identical rows.
- **A candidate is judged on the population it will affect.** The harness trains and replays over every player-week, because training wide won (section 5.16), but scores the comparison on the published population only. Scoring over everyone dilutes a change that helps exactly the players on the site by about a third.
- **The improvement is tested, not just thresholded.** Champion and challenger are scored on identical rows, so the per-row difference in absolute error carries a standard error, and its mean is exactly the difference of the two error rates. A change under two standard errors from zero is rejected however large the raw margin looks. The first candidate tried, a form-to-baseline ratio, came in at 0.08 standard errors with 49.99% of rows improved: a coin flip, and now demonstrably so rather than merely below a threshold.
- **The learning claim is itself measured.** The Report card carries a static-model control line alongside the live system. If the governed loop is not beating a model frozen at the start of the season, the site says so. "Gets smarter" is a published measurement, not a marketing line.
- **Reporting:** a public Report card with weekly and rolling accuracy versus baselines, confidence bands, and misses left visible. If accuracy is flat, the site says so.

### 7.9 Limitations and risks
- Ceiling: about 0.29 R² for fantasy points; about 0.05-0.09 for touchdowns. Week-to-week accuracy will wobble.
- **Weekly improvement may be small or absent.** Our tests found weekly self-adjustment worth 0.7% at best and often negative. The realistic expectation is that a season's worth of experiments yields a few percent in total, with several negative results along the way. The design makes that visible rather than hiding it.
- Our factor tests use a modest, untuned model and 2021-2025; wind and cold samples are small (88 games at 15+ mph).
- Stadium and crowd effects are inferred from proxies; no crowd measurement exists.
- Late injuries and coaching decisions can invalidate a locked prediction.
- Betting lines carry information we cannot fully separate from public information already in team stats.
- Claude adjustments may add nothing; the design measures and drops them if so.

---

## 8. Build plan (before AWS)

1. Data: add advanced stats, charting, participation; build the stadium table and weather (Open-Meteo forecasts and archived forecasts).
2. Point-in-time feature store with leakage tests.
3. Availability model (calibrated from status, practice, position) with tests against the measured rates.
4. Baselines and the walk-forward backtest harness.
5. Team-environment layer, volume shares (with teammate effects), efficiency, touchdown model.
6. Direct model, ensemble, quantile and conformal calibration; factor-by-factor ablation on every layer.
7. Prediction, lock, and grading tables; new published files; Predictions and Report card pages.
8. Experiment ledger and promotion gate (with 5.11 and 5.12 loaded as the first negative results).
9. Wire in the four unexploited datasets (advanced stats, FTN charting, participation, depth charts).
10. Claude feature-discovery routine: failure report -> feature code -> automated walk-forward
    acceptance -> ledger and lessons file.

Everything runs locally and in Docker; no AWS is required.

---

## 9. Reproducibility

`research/common.py`, `a_home_advantage.py`, `a4_team_home_edge.py`, `b_stability_and_touchdowns.py`, `d_context_ablation.py`, `e_models_and_components.py`, `f_weekly_learning.py`, `g_player_learning.py`, `h_error_anatomy.py`, `i_availability.py`; results in `research/results/*.json`. Run each with `.venv\Scripts\python research\<file>.py`.

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
- [Wisdom of the silicon crowd: LLM ensembles rival human crowds](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11800985/)
- [AI-augmented predictions: LLM assistants improve human forecasting](https://dl.acm.org/doi/10.1145/3707649)
- [Claude Help Center: paid plans and the API](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console)
- [Claude Help Center: Claude Code with Pro or Max](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)

*Note on sources: several pages could not be fetched in full (some returned access errors), so those claims rely on search-result summaries and are marked as such above. Every number attributed to "our data" was computed by the scripts listed in section 9.*
