"use client";

import { cn } from "@/lib/utils";
import type { Platform } from "@/lib/types";

export function PlatformIcon({ platform, className }: { platform: Platform; className?: string }) {
  if (platform === "instagram") {
    return (
      <svg viewBox="0 0 24 24" className={cn("h-4 w-4", className)} fill="none" aria-hidden>
        <rect x="3" y="3" width="18" height="18" rx="5" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="17.2" cy="6.8" r="1" fill="currentColor" />
      </svg>
    );
  }
  // LinkedIn
  return (
    <svg viewBox="0 0 24 24" className={cn("h-4 w-4", className)} fill="none" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M7 10v7M7 7.01v.01M11 17v-4.5a2.5 2.5 0 0 1 5 0V17M11 10v7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function PlatformBadge({ platform, className }: { platform: Platform; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-2xs uppercase tracking-wider",
        platform === "instagram"
          ? "border-[#E1306C]/20 bg-[#E1306C]/5 text-[#F472A4]"
          : "border-[#0A66C2]/20 bg-[#0A66C2]/5 text-[#7BB6F8]",
        className,
      )}
    >
      <PlatformIcon platform={platform} />
      {platform === "instagram" ? "Instagram" : "LinkedIn"}
    </span>
  );
}
