import type { Metadata } from "next";
import { ResearchView } from "@/components/ResearchView";

export const metadata: Metadata = {
  title: "Research paper",
  description:
    "The analysis behind the projections: how predictable a single game is, which factors help, whether weekly self-adjustment works, and what I got wrong along the way.",
};

export default function ResearchPage() {
  return <ResearchView />;
}
