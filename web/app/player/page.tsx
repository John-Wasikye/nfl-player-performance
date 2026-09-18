import type { Metadata } from "next";
import { Suspense } from "react";
import { PlayerView } from "@/components/PlayerView";
import { Skeleton } from "@/components/ui";

export const metadata: Metadata = {
  title: "Player",
  description: "A player's rank history and the measures behind their score.",
};

// One static page serves every player: the player id is a query parameter (/player/?id=...), and
// the data is fetched in the browser. That keeps the site independent of which players exist.
export default function PlayerPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <PlayerView />
    </Suspense>
  );
}
