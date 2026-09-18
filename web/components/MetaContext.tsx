"use client";

// meta.json says which season and week are published and when the pipeline last ran. Nearly every
// page needs it, so it is loaded once here and shared.
import { createContext, useContext, type ReactNode } from "react";
import { useJson, type Loaded } from "@/lib/api";
import type { Meta } from "@/lib/types";

const MetaContext = createContext<Loaded<Meta>>({ data: null, error: null, loading: true });

export function MetaProvider({ children }: { children: ReactNode }) {
  const meta = useJson<Meta>("meta.json");
  return <MetaContext.Provider value={meta}>{children}</MetaContext.Provider>;
}

export function useMeta(): Loaded<Meta> {
  return useContext(MetaContext);
}
