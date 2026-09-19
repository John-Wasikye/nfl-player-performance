"use client";

// The two methodology pages answer different questions and people arrive at the wrong one, so each
// carries a visible way across rather than relying on the single "Methodology" item in the header.
import Link from "next/link";
import { cn } from "@/lib/cn";

const PAGES = [
  {
    key: "rankings",
    href: "/methodology/",
    label: "How the rankings work",
    blurb: "Scoring what has already happened",
  },
  {
    key: "predictions",
    href: "/methodology/predictions/",
    label: "How the predictions work",
    blurb: "Projecting what happens next",
  },
] as const;

export function MethodologySwitch({ active }: { active: "rankings" | "predictions" }) {
  return (
    <nav aria-label="Methodology sections" className="grid gap-3 sm:grid-cols-2">
      {PAGES.map((page) => {
        const current = page.key === active;
        return (
          <Link
            key={page.key}
            href={page.href}
            aria-current={current ? "page" : undefined}
            className={cn(
              "rounded-2xl border px-4 py-3 transition-colors",
              current
                ? "border-accent bg-accent-soft"
                : "border-line bg-surface hover:bg-surface-2",
            )}
          >
            <span className="block text-sm font-semibold">{page.label}</span>
            <span className="mt-0.5 block text-xs text-muted">{page.blurb}</span>
          </Link>
        );
      })}
    </nav>
  );
}
