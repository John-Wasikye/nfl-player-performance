import { AUTHOR, linkProps, otherProjectsUrl } from "@/lib/site";
import { ChevronRightIcon } from "./icons";

export function BuiltBy() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-5 py-4 shadow-card">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-fg"
        >
          {AUTHOR.initials}
        </span>
        <div>
          <p className="text-sm text-muted">Designed and built by</p>
          <p className="font-semibold text-fg">{AUTHOR.name}</p>
        </div>
      </div>
      <a
        {...linkProps(otherProjectsUrl())}
        className="inline-flex h-9 items-center gap-1 rounded-lg border border-fg/20 bg-surface px-3.5 text-sm font-medium text-fg shadow-sm transition-colors hover:border-fg/40 hover:bg-surface-2"
      >
        See my other projects
        <ChevronRightIcon width={14} height={14} />
      </a>
    </div>
  );
}
