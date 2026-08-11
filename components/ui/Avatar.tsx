"use client";

import { cn } from "@/lib/utils";
import { initials } from "@/lib/utils";

export function Avatar({
  name,
  size = 28,
  className,
  glow,
}: {
  name: string;
  size?: number;
  className?: string;
  glow?: string;
}) {
  return (
    <span
      className={cn(
        "inline-grid place-items-center rounded-full font-mono text-2xs uppercase tracking-wider bg-ink-800 text-ink-100 border border-ink-600",
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: Math.max(9, Math.round(size * 0.32)),
        boxShadow: glow ? `0 0 0 2px ${glow}22` : undefined,
      }}
    >
      {initials(name)}
    </span>
  );
}
