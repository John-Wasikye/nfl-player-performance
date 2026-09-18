"use client";

// A quick "jump to any player" search, opened with "/" or Ctrl/Cmd+K. It uses the native <dialog>
// element, which gives focus trapping and Escape-to-close for free.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchJson } from "@/lib/api";
import { POSITIONS, type Meta, type Position, type RankingsFile } from "@/lib/types";
import { Avatar } from "./ui";
import { SearchIcon } from "./icons";

interface Entry {
  id: string;
  name: string;
  team: string;
  position: Position;
}

export function useSearchIndex(meta: Meta | null, enabled: boolean) {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!meta || !enabled || entries) return;
    let cancelled = false;
    Promise.all(
      POSITIONS.map((position) =>
        fetchJson<RankingsFile>(`rankings/${meta.season}/${meta.latest_week}/${position}.json`),
      ),
    )
      .then((files) => {
        if (cancelled) return;
        setEntries(
          files.flatMap((file) =>
            file.players.map((p) => ({
              id: p.player_id,
              name: p.name,
              team: p.team,
              position: file.position,
            })),
          ),
        );
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [meta, enabled, entries]);

  return { entries, failed };
}

export function searchEntries(entries: Entry[], query: string, limit = 8): Entry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const starts: Entry[] = [];
  const contains: Entry[] = [];
  for (const entry of entries) {
    const name = entry.name.toLowerCase();
    if (name.startsWith(q) || name.split(" ").some((part) => part.startsWith(q))) starts.push(entry);
    else if (name.includes(q) || entry.team.toLowerCase() === q) contains.push(entry);
  }
  return [...starts, ...contains].slice(0, limit);
}

export function SearchDialog({ meta, opens }: { meta: Meta | null; opens: number }) {
  // `opens` counts how many times the site has asked for the search to open. The native <dialog>
  // owns whether it is actually open (Escape and clicking the backdrop close it on their own), so
  // a request never depends on a flag that could get out of step with what is on screen.
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const { entries, failed } = useSearchIndex(meta, opens > 0);
  const results = useMemo(() => searchEntries(entries ?? [], query), [entries, query]);

  useEffect(() => {
    const element = dialog.current;
    if (opens > 0 && element && !element.open) {
      element.showModal();
      input.current?.focus();
    }
  }, [opens]);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const reset = () => setQuery("");
    element.addEventListener("close", reset);
    return () => element.removeEventListener("close", reset);
  }, []);

  const close = useCallback(() => dialog.current?.close(), []);

  return (
    <dialog
      ref={dialog}
      onClick={(event) => event.target === dialog.current && close()}
      aria-label="Search players"
      className="m-auto mt-[12vh] w-[min(36rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-fg shadow-card"
    >
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <SearchIcon width={18} height={18} className="text-muted" />
        <input
          ref={input}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search players or a team (KC)"
          aria-label="Search players"
          className="w-full bg-transparent text-base outline-none placeholder:text-muted"
        />
        <kbd className="rounded border border-line px-1.5 py-0.5 text-xs text-muted">Esc</kbd>
      </div>
      <div className="max-h-[50vh] overflow-y-auto p-2" aria-live="polite">
        {failed && <p className="px-3 py-6 text-center text-sm text-muted">Search isn&apos;t available right now.</p>}
        {!failed && !entries && <p className="px-3 py-6 text-center text-sm text-muted">Loading players…</p>}
        {!failed && entries && !query.trim() && (
          <p className="px-3 py-6 text-center text-sm text-muted">Type a player&apos;s name.</p>
        )}
        {entries && query.trim() && results.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-muted">No players match &ldquo;{query}&rdquo;.</p>
        )}
        <ul>
          {results.map((entry) => (
            <li key={entry.id}>
              <Link
                href={`/player/?id=${encodeURIComponent(entry.id)}`}
                onClick={close}
                className="flex items-center gap-3 rounded-xl px-3 py-2 hover:bg-surface-2 focus-visible:bg-surface-2"
              >
                <Avatar name={entry.name} team={entry.team} size={32} />
                <span className="flex-1 font-medium">{entry.name}</span>
                <span className="text-sm text-muted">
                  {entry.position} · {entry.team}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </dialog>
  );
}
