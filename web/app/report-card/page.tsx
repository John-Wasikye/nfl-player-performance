import type { Metadata } from "next";
import { ReportCardView } from "@/components/ReportCardView";

export const metadata: Metadata = {
  title: "Report card",
  description:
    "How accurate the projections have been, measured against simple baselines on predictions locked before kickoff, along with every change I've tested, including the ones that failed.",
};

export default function ReportCardPage() {
  return <ReportCardView />;
}
