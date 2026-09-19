"use client";

import Link from "next/link";
import {
  CeilingDiagram,
  LearningLoopDiagram,
  ModelDiagram,
  PopulationDiagram,
  RangeDiagram,
  WeeklyCycleDiagram,
} from "./diagrams";
import { MethodologySwitch } from "./MethodologySwitch";
import { Card, PageHeader, SectionTitle } from "./ui";

function Q({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-line py-4 last:border-b-0">
      <h3 className="font-semibold">{q}</h3>
      <div className="mt-1.5 space-y-2 text-muted">{children}</div>
    </div>
  );
}

const linkClass = "text-accent underline underline-offset-2";

export function PredictionMethodologyView() {
  return (
    <div className="rise">
      <PageHeader
        title="How the predictions work"
        subtitle="How each weekly projection is produced, who gets one, and how I check whether the projections have been any good."
      />
      <MethodologySwitch active="predictions" />

      <div className="mt-8 space-y-12">
        <section>
          <SectionTitle title="Summary" />
          <Card className="p-6">
            <ol className="list-decimal space-y-2 pl-5 text-pretty">
              <li>
                A projection is built mostly from what the player has done recently. That mattered far
                more than anything else I tried adding.
              </li>
              <li>
                Every projection has a range, because one game is too noisy for a single number to mean
                much.
              </li>
              <li>
                Projections are written down before kickoff and never changed, so the accuracy record
                reflects real forecasts.
              </li>
              <li>
                A change to the model only goes in if it beats the current one on past seasons. Changes
                that fail are published too.
              </li>
            </ol>
            <p className="mt-4 text-sm text-muted">
              The analysis behind all of this is in the{" "}
              <Link href="/methodology/predictions/research/" className={linkClass}>
                research paper
              </Link>
              .
            </p>
          </Card>
        </section>

        <section>
          <SectionTitle title="The weekly cycle" />
          <WeeklyCycleDiagram />
          <p className="text-muted">
            The lock is the step that matters. Once a week&apos;s projections are written to disk they
            can&apos;t be rewritten, including by me. Without that, a later run could regenerate last
            week&apos;s numbers with a better model and I could publish the improved score as if it had
            been forecast in advance. The{" "}
            <Link href="/report-card/" className={linkClass}>
              Report card
            </Link>{" "}
            would then be measuring nothing. I run the lock by hand for now, so the record starts once
            the first week has been locked and played.
          </p>
        </section>

        <section>
          <SectionTitle
            title="How a projection is produced"
            description="A ridge regression and gradient boosting, averaged."
          />
          <ModelDiagram />
          <div className="space-y-3 text-muted">
            <p>
              The inputs are recent scoring, how much of the team&apos;s work the player gets, the
              opponent, whether the game is at home, the betting line, and the roof. Weather is in the
              model too, but I haven&apos;t connected a forecast yet, so for games that haven&apos;t been
              played it uses typical values.
            </p>
            <p>
              The two models are a ridge regression, which is linear and stable, and gradient boosting
              (LightGBM), which can pick up combinations of inputs. I average them. More elaborate
              approaches didn&apos;t help. On held-out weeks the ridge reached an R-squared of 0.280,
              boosting 0.288 and the average 0.289, against 0.232 for a plain recent average.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="Prediction intervals"
            description="Quantile models with a split-conformal correction."
          />
          <RangeDiagram />
          <div className="space-y-3 text-muted">
            <p>
              A projection of 24.3 points doesn&apos;t mean the player will score 24.3. The model&apos;s
              range for him is 10.7 to 34.0, and about four times in five the real score should land
              inside it.
            </p>
            <p>
              I check that instead of assuming it. Two extra models estimate the 10th and 90th
              percentiles, and a conformal correction widens them by however much they turned out to be
              too narrow on weeks they hadn&apos;t seen. In the backtest the real score landed inside the
              published range <span className="font-medium text-fg">79.7%</span> of the time, against a
              target of 80%. The Report card shows the same figure for live weeks.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="Which players are projected"
            description="Training, calibration and publication use different groups of players."
          />
          <PopulationDiagram />
          <div className="space-y-3 text-muted">
            <p>
              Players with a small role don&apos;t get a projection. I compared the model with the
              simplest alternative, a player&apos;s own recent average, and below about four points a
              game <span className="font-medium text-fg">the model did worse than that average</span>.
              Publishing those projections would have made the site worse.
            </p>
            <p>
              Players ruled <span className="font-medium text-fg">Out</span> or{" "}
              <span className="font-medium text-fg">Doubtful</span> are left off instead of shown at
              zero, because a zero reads as &ldquo;he will play badly&rdquo; when I mean &ldquo;he
              isn&apos;t playing&rdquo;. A player listed{" "}
              <span className="font-medium text-fg">Questionable</span> keeps his projection for if he
              plays, with the chance he does next to it. That chance comes from how often Questionable
              players played between 2021 and 2025: about 63% overall and 35% for quarterbacks.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="The promotion gate"
            description="How a change is adopted, and why published accuracy can't regress."
          />
          <LearningLoopDiagram />
          <div className="space-y-3 text-muted">
            <p>
              Each week the pipeline reports where the model missed. I have Claude write one new
              feature from that report, as code, and the harness replays five past seasons with and
              without it, on weeks neither version was trained on.
            </p>
            <p>
              The change is adopted only if it is clearly better and the ranges still cover about 80%.
              A tie keeps the current model, so published accuracy can hold or improve but not slip.
            </p>
            <p>
              Changes that fail go on the Report card with their numbers. Most of them fail. The first
              feature I tried, a ratio of recent form to season average, improved 4,231 of 8,464
              predictions, which is a coin flip, so it was rejected.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="The achievable ceiling"
            description="Measured before the engine was built."
          />
          <CeilingDiagram />
          <p className="text-muted">
            An oracle that knew each player&apos;s true season-long average in advance, which is more
            than any model can know, would still miss by about five fantasy points a game. A single game
            is dominated by things nobody can forecast: a tipped pass, a goal-line call, a fumble. My
            model is under 7% away from that bound, which is all the room there is for improvement.
          </p>
        </section>

        <section>
          <SectionTitle title="Limitations" />
          <Card className="px-6 py-2">
            <Q q="It aims at the likely outcome, not the extremes.">
              <p>
                The biggest misses are almost always players who scored far more than expected. A
                34-point game from someone averaging 8 isn&apos;t the most likely result, and the range
                is where that possibility shows up.
              </p>
            </Q>
            <Q q="It only sees what is in the data.">
              <p>
                A coach&apos;s comments, a scheme change nobody has recorded yet or a player&apos;s
                personal situation never reach it. It works from box scores, schedules, injury reports
                and betting lines.
              </p>
            </Q>
            <Q q="Late scratches aren't counted against it.">
              <p>
                A player ruled out shortly before kickoff isn&apos;t graded against the points model.
                That is an availability question, and I track it separately.
              </p>
            </Q>
            <Q q="It is weakest early in the season.">
              <p>Projections lean on recent form, and in week 1 there isn&apos;t much of it.</p>
            </Q>
            <Q q="It only projects fantasy points.">
              <p>
                I haven&apos;t built projections for yards or touchdowns. The research paper explains
                why they are harder to predict than volume.
              </p>
            </Q>
          </Card>
        </section>

        <section>
          <SectionTitle title="Check it yourself" />
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="p-6">
              <h3 className="font-semibold">The Report card</h3>
              <p className="mt-1.5 text-sm text-muted">
                Weekly accuracy against simple baselines, how often the ranges held, and every change
                I&apos;ve tried, including the ones that failed.
              </p>
              <Link
                href="/report-card/"
                className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
              >
                See the record
              </Link>
            </Card>
            <Card className="p-6">
              <h3 className="font-semibold">The research paper</h3>
              <p className="mt-1.5 text-sm text-muted">
                What predicts a game and what doesn&apos;t, how much of it can be predicted at all, and
                the results that ruled out my first design.
              </p>
              <Link
                href="/methodology/predictions/research/"
                className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
              >
                Read the paper
              </Link>
            </Card>
            <Card className="p-6">
              <h3 className="font-semibold">This week&apos;s projections</h3>
              <p className="mt-1.5 text-sm text-muted">
                Every projection with its range and, where relevant, the chance the player takes the
                field.
              </p>
              <Link
                href="/predictions/QB/"
                className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
              >
                See the projections
              </Link>
            </Card>
          </div>
        </section>
      </div>
    </div>
  );
}
