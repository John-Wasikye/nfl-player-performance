import Link from "next/link";
import { EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="space-y-6">
      <EmptyState
        title="Page not found"
        message="That page doesn't exist. Try the rankings or search for a player."
      />
      <div className="flex justify-center gap-3">
        <Link href="/" className="rounded-xl border border-line bg-surface px-5 py-2.5 text-sm font-semibold hover:bg-surface-2">
          Home
        </Link>
        <Link href="/rankings/QB/" className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg hover:opacity-90">
          Rankings
        </Link>
      </div>
    </div>
  );
}
