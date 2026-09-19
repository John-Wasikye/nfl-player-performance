"use client";

// The research paper, rendered from docs/prediction-research.md.
//
// The HTML is generated at build time and inlined rather than fetched, so the paper is present in
// the served markup. It is the substantive part of this project and should be readable without
// JavaScript, indexable, and linkable section by section.
//
// dangerouslySetInnerHTML is safe here in the one case where it is: the input is a file in this
// repository, converted by our own build step, with no user content anywhere in the path.
import Link from "next/link";
import { RESEARCH_HEADINGS, RESEARCH_HTML, RESEARCH_WORDS } from "@/lib/research-generated";
import { MethodologySwitch } from "./MethodologySwitch";
import { Card, PageHeader } from "./ui";

function Contents() {
  return (
    <nav aria-label="Paper contents" className="lg:sticky lg:top-20">
      <Card className="p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Contents</p>
        <ol className="mt-2 space-y-1">
          {RESEARCH_HEADINGS.filter((h) => h.depth === 2).map((heading) => (
            <li key={heading.id}>
              <a
                href={`#${heading.id}`}
                className="block rounded-lg px-2 py-1 text-sm text-muted hover:bg-surface-2 hover:text-fg"
              >
                {heading.text}
              </a>
            </li>
          ))}
        </ol>
      </Card>
    </nav>
  );
}

export function ResearchView() {
  return (
    <div className="rise">
      <PageHeader
        title="Research paper"
        subtitle="The evidence the prediction engine was built from: sixteen studies on six seasons of nflverse data, written before any prediction code existed, including the results that ruled out the original design."
      >
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted">
          <span>{RESEARCH_WORDS.toLocaleString()} words</span>
          <a
            href="/prediction-research.md"
            className="text-accent underline underline-offset-2"
            download
          >
            Download the Markdown
          </a>
          <Link href="/methodology/predictions/" className="text-accent underline underline-offset-2">
            Plain-English summary
          </Link>
        </div>
      </PageHeader>

      <MethodologySwitch active="research" />

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_260px]">
        <article
          className="paper min-w-0"
          dangerouslySetInnerHTML={{ __html: RESEARCH_HTML }}
        />
        <div className="order-first lg:order-none">
          <Contents />
        </div>
      </div>
    </div>
  );
}
