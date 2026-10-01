"use client";

import { cn } from "@/lib/utils";

type Status = "live" | "running" | "pending" | "approved" | "published" | "rejected" | "failed" | "complete" | "idle" | "indexed" | "indexing" | "processing" | "uploading" | "draft" | "awaiting_idea_selection" | "generating_drafts";

const statusMap: Record<Status, { color: string; label: string }> = {
  live: { color: "bg-sodium-500", label: "LIVE" },
  running: { color: "bg-sodium-500", label: "RUNNING" },
  pending: { color: "bg-live-pending", label: "PENDING" },
  approved: { color: "bg-live-ok", label: "APPROVED" },
  published: { color: "bg-live-ok", label: "PUBLISHED" },
  rejected: { color: "bg-live-reject", label: "REJECTED" },
  failed: { color: "bg-live-reject", label: "FAILED" },
  complete: { color: "bg-live-ok", label: "DONE" },
  idle: { color: "bg-ink-400", label: "IDLE" },
  indexed: { color: "bg-live-ok", label: "INDEXED" },
  indexing: { color: "bg-sodium-500", label: "INDEXING" },
  processing: { color: "bg-sodium-500", label: "PROCESSING" },
  uploading: { color: "bg-sodium-500", label: "UPLOADING" },
  draft: { color: "bg-ink-400", label: "DRAFT" },
  awaiting_idea_selection: { color: "bg-live-pending", label: "PICKING IDEAS" },
  generating_drafts: { color: "bg-sodium-500", label: "GENERATING" },
};

export function StatusDot({ status, withLabel, className }: { status: Status; withLabel?: boolean; className?: string }) {
  const meta = statusMap[status] ?? statusMap.idle;
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="relative inline-flex h-1.5 w-1.5">
        <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", meta.color)} />
      </span>
      {withLabel && (
        <span className="font-mono text-2xs uppercase tracking-wider text-ink-200">{meta.label}</span>
      )}
    </span>
  );
}
