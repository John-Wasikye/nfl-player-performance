"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { isStale, timeAgo } from "@/lib/format";
import { MetaProvider, useMeta } from "./MetaContext";
import { SearchDialog } from "./SearchDialog";
import { ThemeToggle } from "./ThemeToggle";
import { AlertIcon, SearchIcon } from "./icons";

const NAV = [
  { href: "/", label: "Home", match: (p: string) => p === "/" },
  { href: "/rankings/QB/", label: "Rankings", match: (p: string) => p.startsWith("/rankings") || p.startsWith("/player") },
  { href: "/methodology/", label: "Methodology", match: (p: string) => p.startsWith("/methodology") },
  { href: "/about/", label: "About", match: (p: string) => p.startsWith("/about") },
];

function Header({ onSearch }: { onSearch: () => void }) {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 px-4 sm:h-14 sm:flex-nowrap sm:px-6">
        <Link href="/" className="flex h-12 items-center gap-2 font-semibold tracking-tight sm:h-auto">
          <span
            aria-hidden="true"
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-xs font-bold text-accent-fg"
          >
            PP
          </span>
          <span className="hidden sm:inline">Player Performance</span>
        </Link>
        <nav
          aria-label="Primary"
          className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto pb-2 sm:order-none sm:mx-0 sm:w-auto sm:flex-1 sm:overflow-visible sm:pb-0"
        >
          {NAV.map((item) => {
            const current = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium",
                  current ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <span className="flex-1 sm:hidden" aria-hidden="true" />
        <button
          type="button"
          onClick={onSearch}
          aria-label="Search players"
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm text-muted hover:text-fg"
        >
          <SearchIcon width={15} height={15} />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden rounded border border-line px-1 text-xs sm:inline">/</kbd>
        </button>
        <ThemeToggle />
      </div>
    </header>
  );
}

function StaleBanner() {
  const { data } = useMeta();
  // The current time is only known in the browser. The server snapshot is null, so the server
  // render and the first client render agree, and the banner appears after hydration.
  const minute = useSyncExternalStore(
    () => () => {},
    () => Math.floor(Date.now() / 60000),
    () => null,
  );
  if (!data || minute === null) return null;
  const now = new Date(minute * 60000);
  if (!isStale(data.generated_at, now)) return null;
  return (
    <div role="status" className="border-b border-line bg-warn-soft text-warn">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-sm sm:px-6">
        <AlertIcon width={16} height={16} />
        <span>
          These rankings were last updated {timeAgo(data.generated_at, now)}. Newer results may not be
          included yet.
        </span>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto max-w-6xl space-y-2 px-4 py-8 text-sm text-muted sm:px-6">
        <p>
          Data from{" "}
          <a className="underline underline-offset-2 hover:text-fg" href="https://github.com/nflverse/nflverse-data">
            nflverse
          </a>{" "}
          (
          <a className="underline underline-offset-2 hover:text-fg" href="https://creativecommons.org/licenses/by/4.0/">
            CC BY 4.0
          </a>
          ).
        </p>
        <p>
          Independent project. Not affiliated with or endorsed by the NFL or any team. Statistical
          rankings only, not betting or financial advice.
        </p>
      </div>
    </footer>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const { data: meta } = useMeta();
  const [searchOpens, setSearchOpens] = useState(0);
  const openSearch = () => setSearchOpens((count) => count + 1);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        setSearchOpens((count) => count + 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-accent-fg"
      >
        Skip to content
      </a>
      <Header onSearch={openSearch} />
      <StaleBanner />
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
        {children}
      </main>
      <Footer />
      <SearchDialog meta={meta} opens={searchOpens} />
    </>
  );
}

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <MetaProvider>
      <Shell>{children}</Shell>
    </MetaProvider>
  );
}
