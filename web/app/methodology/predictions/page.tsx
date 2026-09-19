import type { Metadata } from "next";
import { PredictionMethodologyView } from "@/components/PredictionMethodologyView";

export const metadata: Metadata = {
  title: "How the predictions work",
  description:
    "In plain English: how each weekly projection is built, why every one carries a range, who gets projected and who does not, how the system improves, and what it honestly cannot do.",
};

export default function PredictionMethodologyPage() {
  return <PredictionMethodologyView />;
}
