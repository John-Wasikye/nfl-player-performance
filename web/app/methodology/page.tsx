import type { Metadata } from "next";
import { MethodologyView } from "@/components/MethodologyView";

export const metadata: Metadata = {
  title: "Methodology",
  description: "How the composite score and fantasy ranking are built, and how well they predict the next week.",
};

export default function MethodologyPage() {
  return <MethodologyView />;
}
