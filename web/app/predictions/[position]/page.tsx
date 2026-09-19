import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PredictionsView } from "@/components/PredictionsView";
import { isPosition, POSITION_NAMES, POSITIONS } from "@/lib/types";

// Only the five positions exist, so every page is generated at build time.
export const dynamicParams = false;

export function generateStaticParams() {
  return POSITIONS.map((position) => ({ position }));
}

export async function generateMetadata({ params }: PageProps<"/predictions/[position]">): Promise<Metadata> {
  const { position } = await params;
  if (!isPosition(position)) return {};
  return {
    title: `${POSITION_NAMES[position]} projections`,
    description: `Next-game fantasy point projections for ${POSITION_NAMES[position]}, each with the 80% range it sits in and the chance the player takes the field.`,
  };
}

export default async function PredictionsPage({ params }: PageProps<"/predictions/[position]">) {
  const { position } = await params;
  if (!isPosition(position)) notFound();
  return <PredictionsView position={position} />;
}
