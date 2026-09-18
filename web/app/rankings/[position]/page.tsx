import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RankingsView } from "@/components/RankingsView";
import { Skeleton } from "@/components/ui";
import { isPosition, POSITION_NAMES, POSITIONS } from "@/lib/types";

// Only the five positions exist, so every page is generated at build time.
export const dynamicParams = false;

export function generateStaticParams() {
  return POSITIONS.map((position) => ({ position }));
}

export async function generateMetadata({ params }: PageProps<"/rankings/[position]">): Promise<Metadata> {
  const { position } = await params;
  if (!isPosition(position)) return {};
  return {
    title: `${POSITION_NAMES[position]} rankings`,
    description: `${POSITION_NAMES[position]} ranked by composite performance score and PPR fantasy points, updated daily.`,
  };
}

export default async function RankingsPage({ params }: PageProps<"/rankings/[position]">) {
  const { position } = await params;
  if (!isPosition(position)) notFound();
  return (
    // useSearchParams in the view needs a Suspense boundary for static export.
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <RankingsView position={position} />
    </Suspense>
  );
}
