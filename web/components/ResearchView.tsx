import Link from "next/link";
import { RESEARCH_HEADINGS, RESEARCH_HTML } from "@/lib/research-generated";
import { MethodologySwitch } from "./MethodologySwitch";
import { Card } from "./ui";

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

// The HTML comes from docs/prediction-research.md through scripts/build-research.mjs at build time.
export function ResearchView() {
  return (
    <div className="rise">
      <MethodologySwitch active="predictions" />
      <p className="mt-6 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <Link
          href="/methodology/predictions/"
          className="text-accent underline underline-offset-2"
        >
          Back to how the predictions work
        </Link>
        <a
          href="/prediction-research.md"
          className="text-accent underline underline-offset-2"
          download
        >
          Download as Markdown
        </a>
      </p>

      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_260px]">
        <article className="paper min-w-0" dangerouslySetInnerHTML={{ __html: RESEARCH_HTML }} />
        <div className="order-first lg:order-none">
          <Contents />
        </div>
      </div>
    </div>
  );
}
