"use client";

import { cn } from "@/lib/utils";

export function Chip({
  label,
  className,
  tone = "default",
}: {
  label: string;
  className?: string;
  tone?: "default" | "sodium" | "steel" | "success" | "danger" | "muted";
}) {
  const tones = {
    default: "border-ink-600 bg-ink-800 text-ink-100",
    sodium: "border-sodium-500/30 bg-sodium-500/10 text-sodium-300",
    steel: "border-steel-500/30 bg-steel-500/10 text-steel-400",
    success: "border-live-ok/30 bg-live-ok/10 text-live-ok",
    danger: "border-live-reject/30 bg-live-reject/10 text-live-reject",
    muted: "border-ink-700 bg-ink-850 text-ink-200",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-2xs uppercase tracking-wider",
        tones[tone],
        className,
      )}
    >
      {label}
    </span>
  );
}
