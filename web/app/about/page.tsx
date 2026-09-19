import type { Metadata } from "next";
import { ContactForm } from "@/components/ContactForm";
import { Card, PageHeader } from "@/components/ui";
import { AUTHOR, linkProps, otherProjectsUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "About & data",
  description: "Where the data comes from, how often it updates, and what the terms mean.",
};

const GLOSSARY: Array<[string, string]> = [
  ["EPA (expected points added)", "How much a play changed the team's expected points. A positive number means the play helped the offense."],
  ["CPOE", "Completion percentage over expected: how a quarterback's completion rate compares with what the throws would normally produce."],
  ["RACR", "Receiver air conversion ratio: receiving yards divided by air yards, a measure of how well a receiver turns targets into yards."],
  ["WOPR", "Weighted opportunity rating: a blend of a receiver's share of the team's targets and air yards."],
  ["Target share / air yards share", "The fraction of the team's targets or air yards that went to the player."],
  ["PPR", "Points per reception: fantasy scoring that gives a point for every catch."],
  ["Percentile", "Where a player sits among their position group: the 90th percentile means better than 90% of them."],
];

export default function AboutPage() {
  return (
    <div className="rise space-y-10">
      <PageHeader
        title="About & data"
        subtitle="An independent project that turns public NFL data into position rankings and weekly projections."
      />

      <section aria-label="About the author">
        <Card className="flex flex-col gap-5 p-6 sm:flex-row sm:items-start">
          <span
            aria-hidden="true"
            className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent text-lg font-bold text-accent-fg"
          >
            {AUTHOR.initials}
          </span>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold tracking-tight">Built by {AUTHOR.name}</h2>
            <p className="mt-1 text-sm text-muted">
              I designed and built the site, the data pipeline and the prediction engine myself. The
              code is public.
            </p>
            <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted">Other projects</dt>
              <dd>
                <a className="text-accent underline underline-offset-2" {...linkProps(otherProjectsUrl())}>
                  See my other projects
                </a>
              </dd>
              <dt className="text-muted">Source code</dt>
              <dd>
                <a className="text-accent underline underline-offset-2" {...linkProps(AUTHOR.repo)}>
                  nfl-player-performance on GitHub
                </a>
              </dd>
            </dl>
          </div>
        </Card>
      </section>

      <section aria-label="Contact">
        <Card className="p-6">
          <h2 className="text-lg font-semibold tracking-tight">Send me a message</h2>
          <p className="mt-1 mb-4 text-sm text-muted">
            Questions about the project, the method, or the code are welcome.
          </p>
          <ContactForm />
        </Card>
      </section>

      <section aria-label="Data sources" className="grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-semibold">Where the data comes from</h2>
          <p className="mt-2 text-sm text-muted">
            All statistics come from{" "}
            <a className="text-accent underline underline-offset-2" href="https://github.com/nflverse/nflverse-data">
              nflverse
            </a>
            , an open community project, and are used under the{" "}
            <a className="text-accent underline underline-offset-2" href="https://creativecommons.org/licenses/by/4.0/">
              Creative Commons Attribution 4.0
            </a>{" "}
            license.
          </p>
        </Card>
        <Card className="p-6">
          <h2 className="font-semibold">How often it updates</h2>
          <p className="mt-2 text-sm text-muted">
            The pipeline runs once a day during the season, after the previous night&apos;s games have
            been added to the source data. The page header shows when the rankings were last refreshed.
            If a refresh is more than a day and a half late, a notice appears at the top of every page.
          </p>
        </Card>
      </section>

      <section aria-label="Glossary">
        <h2 className="mb-4 text-lg font-semibold tracking-tight">Glossary</h2>
        <Card>
          <dl className="divide-y divide-line">
            {GLOSSARY.map(([term, meaning]) => (
              <div key={term} className="grid gap-1 px-5 py-4 sm:grid-cols-[14rem_1fr] sm:gap-6">
                <dt className="font-medium">{term}</dt>
                <dd className="text-sm text-muted">{meaning}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </section>

    </div>
  );
}
