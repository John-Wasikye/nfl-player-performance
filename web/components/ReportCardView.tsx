"use client";

import { useJson } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatPercent } from "@/lib/format";
import type { AccuracyFile, GradedWeek, LedgerEntry, LedgerFile } from "@/lib/types";
import { useMeta } from "./MetaContext";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SectionTitle, Skeleton } from "./ui";

function bestBaseline(week: GradedWeek): { name: string; mae: number } | null {
  const entries = Object.entries(week.baseline_mae);
  if (entries.length === 0) return null;
  const [name, mae] = entries.reduce((a, b) => (b[1] < a[1] ? b : a));
  return { name: name.replace(/_/g, " "), mae };
}

function Margin({ week }: { week: GradedWeek }) {
  const baseline = bestBaseline(week);
  if (!baseline) return <span className="text-muted">—</span>;
  const margin = baseline.mae - week.mae;
  // Under 0.15 ahead counts as too close to call, so it isn't coloured as a win.
  const tone = margin >= 0.15 ? "up" : margin <= -0.05 ? "down" : "neutral";
  return (
    <span
      className={cn(
        "tnum font-medium",
        tone === "up" && "text-up",
        tone === "down" && "text-down",
        tone === "neutral" && "text-muted",
      )}
    >
      {margin >= 0 ? "+" : ""}
      {margin.toFixed(3)}
    </span>
  );
}

function WeeklyTable({ weeks }: { weeks: GradedWeek[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">
          Accuracy by week: mean absolute error against the best simple baseline, with the number of
          player-games each figure is based on.
        </caption>
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th scope="col" className="px-4 py-2 font-medium">Week</th>
            <th scope="col" className="px-4 py-2 font-medium">Players</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Avg error</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Best baseline</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Margin</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Range hit</th>
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => {
            const baseline = bestBaseline(week);
            return (
              <tr key={week.week} className="border-b border-line last:border-b-0">
                <th scope="row" className="px-4 py-2 text-left font-medium">{week.week}</th>
                <td className="px-4 py-2 text-muted tnum">{week.player_games.toLocaleString()}</td>
                <td className="px-4 py-2 text-right tnum">{week.mae.toFixed(2)}</td>
                <td className="px-4 py-2 text-right text-muted tnum">
                  {baseline ? baseline.mae.toFixed(2) : "—"}
                </td>
                <td className="px-4 py-2 text-right"><Margin week={week} /></td>
                <td className="px-4 py-2 text-right text-muted tnum">
                  {formatPercent(week.interval_coverage)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LedgerRow({ entry }: { entry: LedgerEntry }) {
  const judgedOnMargin = entry.metric === "margin_over_baseline";
  return (
    <li className="border-b border-line px-4 py-4 last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-medium">{entry.change}</p>
        {entry.promoted ? <Badge tone="up">Kept</Badge> : <Badge tone="neutral">Rejected</Badge>}
      </div>
      <p className="mt-1 text-sm text-muted">{entry.hypothesis}</p>
      <p className="mt-2 text-sm">
        <span className="text-muted">Result: </span>
        {entry.reason}
      </p>
      <p className="mt-1 text-xs text-muted tnum">
        {judgedOnMargin ? "Margin over baseline" : "Average error"} {entry.champion_score} →{" "}
        {entry.challenger_score}
        {judgedOnMargin && " (not average error, because this change altered which players are predicted)"}
      </p>
    </li>
  );
}

export function ReportCardView() {
  const meta = useMeta();
  const season = meta.data?.season ?? null;
  const accuracy = useJson<AccuracyFile>(season ? `accuracy/${season}.json` : null);
  const ledger = useJson<LedgerFile>("ledger.json");

  const error = meta.error ?? accuracy.error;
  const loading = meta.loading || accuracy.loading;
  const graded = accuracy.data?.weeks ?? [];
  const total = accuracy.data?.season_to_date ?? null;

  return (
    <>
      <PageHeader
        title="Report card"
        subtitle="Projections are written down before kickoff and never changed, so this page measures forecasts, not hindsight. If the model is losing to a plain average, it says so here."
      />

      {error ? (
        <ErrorState message={error.message} />
      ) : loading ? (
        <Skeleton className="h-64 w-full rounded-2xl" />
      ) : (
        <div className="flex flex-col gap-8">
          <Card as="section" className="p-5">
            <SectionTitle title="Where things stand" />
            <p className="text-pretty">{accuracy.data?.verdict}</p>
            {total && (
              <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted">Average error</dt>
                  <dd className="text-xl font-semibold tnum">{total.mae.toFixed(2)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">Player-games</dt>
                  <dd className="text-xl font-semibold tnum">
                    {total.player_games.toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">Margin over baseline</dt>
                  <dd className="text-xl font-semibold"><Margin week={total} /></dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">80% range hit</dt>
                  <dd className="text-xl font-semibold tnum">
                    {formatPercent(total.interval_coverage)}
                  </dd>
                </div>
              </dl>
            )}
          </Card>

          <section>
            <SectionTitle
              title="Week by week"
              description="Average error depends on how many and which players are included, so each week shows its player count."
            />
            {graded.length === 0 ? (
              <EmptyState
                title="Nothing graded yet"
                message="A week is graded once its games have been played."
              />
            ) : (
              <Card>
                <WeeklyTable weeks={graded} />
              </Card>
            )}
          </section>

          <section>
            <SectionTitle
              title="What has been tried"
              description="Every change I've tested against the current model, including the ones that failed. A change is kept only if it beats the current model on weeks neither was trained on."
            />
            {ledger.data && ledger.data.entries.length > 0 ? (
              <Card>
                <ul>
                  {ledger.data.entries.map((entry) => (
                    <LedgerRow key={entry.entry_id} entry={entry} />
                  ))}
                </ul>
              </Card>
            ) : (
              <EmptyState title="No experiments graded yet" />
            )}
          </section>

          <section>
            <SectionTitle title="How to read this" />
            <Card className="p-5">
              <dl className="flex flex-col gap-4 text-sm">
                <div>
                  <dt className="font-medium">Average error</dt>
                  <dd className="text-muted">
                    The average distance between the projection and the real score, in fantasy points. Better players are more variable, so it goes up when the player group gets stricter even if the model improves. Only compare it across weeks with the same group of players.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium">Margin over baseline</dt>
                  <dd className="text-muted">
                    How much better than using the player&apos;s own recent average, measured on the same players. I treat anything under 0.15 as too small to claim.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium">80% range hit</dt>
                  <dd className="text-muted">
                    How often the real score landed inside the range shown with the projection. It should be close to 80%. Much lower means the ranges are too narrow, and much higher means they are wider than they need to be.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium">The frozen control</dt>
                  <dd className="text-muted">
                    A model fixed before the season and never updated, scored on the same games. If the live model isn&apos;t beating it, nothing I&apos;ve added during the season has helped.
                  </dd>
                </div>
              </dl>
            </Card>
          </section>
        </div>
      )}
    </>
  );
}
