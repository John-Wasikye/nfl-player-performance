"use client";

// How the predictions work, in plain English.
//
// Written for someone who has never read a statistics paper. Every claim with a number behind it is
// a real measurement from the research, and where the answer is unflattering it says so, because a
// methodology page that only explains the good parts is advertising.

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

export function PredictionMethodologyView() {
  return (
    <div className="rise">
      <PageHeader
        title="How the predictions work"
        subtitle="Every week the site projects what each player will score in their next game. This page explains how that number is produced, what it can and cannot do, and how you can check whether it has been any good."
      />
      <MethodologySwitch active="predictions" />

      <div className="mt-8 space-y-12">
        <section>
          <SectionTitle
            title="The short version"
            description="Four sentences, if you read nothing else."
          />
          <Card className="p-6">
            <ol className="list-decimal space-y-2 pl-5 text-pretty">
              <li>
                A projection is mostly built from what a player has been doing lately, because that
                turns out to matter far more than anything else we could add.
              </li>
              <li>
                Every projection comes with a range, because one game of football is genuinely
                unpredictable and a single number would claim a precision that does not exist.
              </li>
              <li>
                Projections are written down before kickoff and never changed, so the accuracy we
                publish is forecasting rather than hindsight.
              </li>
              <li>
                Improvements have to prove themselves on past seasons before they ship, and the ones
                that fail are published too.
              </li>
            </ol>
          </Card>
        </section>

        <section>
          <SectionTitle
            title="What happens each week"
            description="The order matters more than it looks."
          />
          <WeeklyCycleDiagram />
          <p className="text-muted">
            The step that does the work is the lock. Once a week&apos;s projections are written to
            disk they cannot be rewritten, even by us. Without that, a later run could quietly
            regenerate last week&apos;s numbers with a better model and publish the improved score as
            though it had been forecast in advance, and the{" "}
            <Link href="/report-card/" className="text-accent underline underline-offset-2">
              Report card
            </Link>{" "}
            would be measuring nothing at all.
          </p>
        </section>

        <section>
          <SectionTitle
            title="Where the number comes from"
            description="Two ordinary models, averaged. No magic."
          />
          <ModelDiagram />
          <div className="space-y-3 text-muted">
            <p>
              The inputs are the things you would expect: how many points the player has scored
              recently, how much of his team&apos;s work he has been getting, who he is playing, whether
              the game is at home, what the betting line says about how high-scoring it will be, and
              the weather if the stadium is open.
            </p>
            <p>
              Those feed two different models. One is a straight-line model that is steady and hard to
              fool. The other builds decision trees and can spot combinations the first one misses.
              Their answers are averaged.
            </p>
            <p className="text-fg">
              We tried more complicated approaches and they did not help. The limit here is the sport,
              not the software: single-game fantasy scoring is close to a coin toss dressed up in
              numbers, and no model reads a coin toss.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="Why there is always a range"
            description="This is the part most projection sites leave out."
          />
          <RangeDiagram />
          <div className="space-y-3 text-muted">
            <p>
              A projection of 24.3 points reads like a promise. It is not one. What the model actually
              believes is closer to &ldquo;probably somewhere between 11 and 34, most likely around
              24&rdquo;, and hiding that behind one number would be misleading.
            </p>
            <p>
              The range is checked rather than asserted. We measure how often the real score actually
              landed inside the published range on weeks the model had never seen, and widen the
              ranges until that figure is right. The target is 80%, and the last measurement was{" "}
              <span className="font-medium text-fg">79.7%</span>. If it drifts, the Report card says
              so.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="Who gets a projection, and who does not"
            description="Not everyone should have one."
          />
          <PopulationDiagram />
          <div className="space-y-3 text-muted">
            <p>
              Players with a very small role are left out on purpose. We measured the model against
              the simplest possible alternative, just using a player&apos;s own recent average, and
              below about four points a game{" "}
              <span className="font-medium text-fg">the model was worse than that average</span>.
              Publishing those projections would make the site less useful than doing nothing.
            </p>
            <p>
              Players ruled <span className="font-medium text-fg">Out</span> or{" "}
              <span className="font-medium text-fg">Doubtful</span> are not shown at all rather than
              shown at zero, because a zero reads like &ldquo;he will play badly&rdquo; when we mean
              &ldquo;he is not playing&rdquo;. Players listed{" "}
              <span className="font-medium text-fg">Questionable</span> keep their projection for if
              they play, with the chance they do beside it. That chance is measured from how often
              questionable players actually took the field: about 63% overall, and only about 35% for
              quarterbacks.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="How it gets better, and why it cannot get worse"
            description="The part people usually just assert."
          />
          <LearningLoopDiagram />
          <div className="space-y-3 text-muted">
            <p>
              Each week the system summarises where it missed. One new idea is written as actual code
              that measures something the model has never seen. That idea is then replayed against
              five past seasons, side by side with the current model, on weeks neither of them was
              trained on.
            </p>
            <p>
              It only ships if it is clearly better and its ranges are still honest. A tie keeps the
              current model. That is what makes published accuracy a ratchet: it can click forward or
              hold, but it does not slip backwards because nothing untested ever gets in.
            </p>
            <p className="text-fg">
              Ideas that fail are published too, with their numbers, on the Report card. Most ideas
              fail. A page showing only the ones that worked would suggest a system that improves
              whenever someone touches it, which is the opposite of what we found.
            </p>
          </div>
        </section>

        <section>
          <SectionTitle
            title="How good can this realistically get?"
            description="We measured the ceiling before building anything."
          />
          <CeilingDiagram />
          <p className="text-muted">
            This is worth being blunt about. Suppose you had a crystal ball that told you each
            player&apos;s true season-long average before the season started. That is far more than
            any model can know. It would still be wrong by about five fantasy points a game, because
            single games are dominated by things nobody can forecast: a tipped pass, a goal-line
            call, a fumble. The entire gap between this model and that crystal ball is under 7%.
            Anyone promising dramatically more than that is not measuring.
          </p>
        </section>

        <section>
          <SectionTitle title="Honest limitations" description="Things this cannot do." />
          <Card className="px-6 py-2">
            <Q q="It cannot predict a breakout game.">
              <p>
                The biggest misses are almost always players who scored far more than expected. A
                model aims at the most likely outcome, and a 34-point game from someone averaging 8
                is, by definition, not the most likely outcome. The range is where that possibility
                lives.
              </p>
            </Q>
            <Q q="It does not know anything that is not in the data.">
              <p>
                A coach saying something in a press conference, a player&apos;s personal
                circumstances, a scheme change nobody has recorded yet: none of that reaches the
                model. It sees box scores, schedules, injury reports and betting lines.
              </p>
            </Q>
            <Q q="Late scratches are not its fault, and are not counted against it.">
              <p>
                If a player is ruled out ninety minutes before kickoff, that is an availability
                question, not a scoring one. Those are tracked separately rather than graded as
                missed projections.
              </p>
            </Q>
            <Q q="Early in a season it knows less.">
              <p>
                Projections lean on recent form, and in week 1 there is very little of it. Accuracy
                against the simple baseline is widest early and narrows as the season goes on.
              </p>
            </Q>
          </Card>
        </section>

        <section>
          <SectionTitle
            title="Check it yourself"
            description="The whole point of publishing the record."
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Card className="p-6">
              <h3 className="font-semibold">The Report card</h3>
              <p className="mt-1.5 text-sm text-muted">
                Week by week accuracy against the simple baselines, how often the ranges were right,
                and every change that has been tried, including the failures.
              </p>
              <Link
                href="/report-card/"
                className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
              >
                See the record
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
