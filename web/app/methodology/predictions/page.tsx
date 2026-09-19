import type { Metadata } from "next";
import { PredictionMethodologyView } from "@/components/PredictionMethodologyView";

export const metadata: Metadata = {
  title: "How the predictions work",
  description:
    "How each weekly projection is produced, who gets one, how a change to the model is adopted, and what the model can't do.",
};

export default function PredictionMethodologyPage() {
  return <PredictionMethodologyView />;
}
