"use client";

import { cn } from "@/lib/utils";

type Status = "live" | "running" | "pending" | "approved" | "published" | "rejected" | "failed" | "complete" | "idle" | "indexed" | "indexing" | "processing" | "uploading" | "draft";

const statusMap: Record<Status, { color: string; label: string; pulse?: boolean }> = {
  live: { color: "bg-sodium-500", label: "LIVE", pulse: true },
  running: { color: "bg-sodium-500", label: "RUNNING", pulse: true },
  pending: { color: "bg-live-pending", label: "PENDING" },
  approved: { color: "bg-live-ok", label: "APPROVED" },
  published: { color: "bg-live-ok", label: "PUBLISHED" },
  rejected: { color: "bg-live-reject", label: "REJECTED" },
  failed: { color: "bg-live-reject", label: "FAILED" },
  complete: { color: "bg-live-ok", label: "DONE" },
  idle: { color: "bg-ink-400", label: "IDLE" },
  indexed: { color: "bg-live-ok", label: "INDEXED" },
  indexing: { color: "bg-sodium-500", label: "INDEXING", pulse: true },
  processing: { color: "bg-sodium-500", label: "PROCESSING", pulse: true },
  uploading: { color: "bg-sodium-500", label: "UPLOADING", pulse: true },
  draft: { color: "bg-ink-400", label: "DRAFT" },
};

export function StatusDot({ status, withLabel, className }: { status: Status; withLabel?: boolean; className?: string }) {
  const meta = statusMap[status] ?? statusMap.idle;
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="relative inline-flex h-1.5 w-1.5">
        {meta.pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-60 animate-pulse-ring",
              meta.color,
            )}
          />
        )}
        <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", meta.color)} />
      </span>
      {withLabel && (
        <span className="font-mono text-2xs uppercase tracking-wider text-ink-200">{meta.label}</span>
      )}
    </span>
  );
}
