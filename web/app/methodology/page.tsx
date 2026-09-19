import type { Metadata } from "next";
import { MethodologyView } from "@/components/MethodologyView";

export const metadata: Metadata = {
  title: "How the rankings work",
  description:
    "In plain English: how a player's composite score is put together, what each setting means, and how well the rankings hold up when tested against later seasons.",
};

export default function MethodologyPage() {
  return <MethodologyView />;
}
