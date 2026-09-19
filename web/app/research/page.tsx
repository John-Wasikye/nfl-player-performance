import type { Metadata } from "next";
import { ResearchView } from "@/components/ResearchView";

export const metadata: Metadata = {
  title: "Research paper",
  description:
    "Sixteen empirical studies on six seasons of nflverse data, measuring what actually predicts weekly NFL fantasy performance: the achievable ceiling, which statistics are skill rather than luck, whether weekly self-adjustment works, and which players are worth predicting at all.",
};

export default function ResearchPage() {
  return <ResearchView />;
}
