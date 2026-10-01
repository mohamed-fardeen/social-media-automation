"use client";

import { useEffect } from "react";
import { bootstrapRealtime } from "@/lib/store";

export function BootstrapRealtime() {
  useEffect(() => {
    bootstrapRealtime();
  }, []);
  return null;
}
