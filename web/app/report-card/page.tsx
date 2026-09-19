import type { Metadata } from "next";
import { ReportCardView } from "@/components/ReportCardView";

export const metadata: Metadata = {
  title: "Report card",
  description:
    "How accurate the projections have actually been, measured against simple baselines on predictions locked before kickoff, with every experiment that was tried and rejected.",
};

export default function ReportCardPage() {
  return <ReportCardView />;
}
