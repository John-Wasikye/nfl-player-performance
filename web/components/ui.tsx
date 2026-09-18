"use client";

// Small building blocks used across the site.
import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";
import { readableTextColor, teamColor } from "@/lib/teams";
import { POSITION_NAMES, POSITIONS, type Position } from "@/lib/types";
import { AlertIcon, ArrowDownIcon, ArrowUpIcon, InfoIcon } from "./icons";

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag className={cn("rounded-2xl border border-line bg-surface shadow-card", className)}>
      {children}
    </Tag>
  );
}

export function SectionTitle({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "up" | "down" | "warn";
}) {
  const tones = {
    neutral: "bg-surface-2 text-muted",
    accent: "bg-accent-soft text-accent",
    up: "bg-up-soft text-up",
    down: "bg-down-soft text-down",
    warn: "bg-warn-soft text-warn",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

/** A player avatar: initials on the team color. No photos, no logos. */
export function Avatar({
  name,
  team,
  size = 36,
}: {
  name: string;
  team: string;
  size?: number;
}) {
  const background = teamColor(team);
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold ring-1 ring-fg/20"
      style={{
        width: size,
        height: size,
        background,
        color: readableTextColor(background),
        fontSize: size * 0.38,
      }}
    >
      {initials(name)}
    </span>
  );
}

/** How a player's rank changed since last week. Never relies on color alone. */
export function MovementChip({
  movement,
  isNew,
}: {
  movement: number | null;
  isNew?: boolean;
}) {
  if (isNew) {
    return <Badge tone="accent">NEW</Badge>;
  }
  if (movement === null) {
    return <span className="text-xs text-muted">{"—"}</span>;
  }
  if (movement === 0) {
    return (
      <span className="text-xs text-muted" aria-label="No change">
        {"–"}
      </span>
    );
  }
  const up = movement > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-semibold tnum",
        up ? "text-up" : "text-down",
      )}
      aria-label={`${up ? "Up" : "Down"} ${Math.abs(movement)} ${Math.abs(movement) === 1 ? "place" : "places"}`}
    >
      {up ? <ArrowUpIcon width={12} height={12} /> : <ArrowDownIcon width={12} height={12} />}
      {Math.abs(movement)}
    </span>
  );
}

export function InjuryBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const tone = status === "Out" ? "down" : status === "Doubtful" ? "down" : "warn";
  return <Badge tone={tone}>{status}</Badge>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden="true" />;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface px-6 py-12 text-center"
    >
      <AlertIcon width={28} height={28} className="text-down" />
      <div>
        <p className="font-semibold">{title}</p>
        <p className="mt-1 text-sm text-muted">{message}</p>
      </div>
      <button
        type="button"
        onClick={onRetry ?? (() => window.location.reload())}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-line px-6 py-12 text-center">
      <InfoIcon width={24} height={24} className="text-muted" />
      <p className="font-medium">{title}</p>
      {message && <p className="max-w-md text-sm text-muted">{message}</p>}
    </div>
  );
}

/** Position navigation, as real links so each position has its own URL. */
export function PositionTabs({ active }: { active?: Position }) {
  return (
    <nav aria-label="Positions" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
      {POSITIONS.map((position) => {
        const current = position === active;
        return (
          <Link
            key={position}
            href={`/rankings/${position}/`}
            aria-current={current ? "page" : undefined}
            title={POSITION_NAMES[position]}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
              current
                ? "bg-fg text-bg"
                : "bg-surface-2 text-muted hover:text-fg",
            )}
          >
            {position}
          </Link>
        );
      })}
    </nav>
  );
}

/** A two-or-more option toggle, used to switch between the composite and fantasy views. */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-xl bg-surface-2 p-1"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors",
              selected ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="mb-6">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
      {subtitle && <p className="mt-2 max-w-2xl text-muted">{subtitle}</p>}
      {children}
    </header>
  );
}

