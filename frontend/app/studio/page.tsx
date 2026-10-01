"use client";

import Link from "next/link";
import { useDraftsLive } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlatformBadge } from "@/components/ui/PlatformIcon";
import { StatusDot } from "@/components/ui/StatusDot";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import { CreateDraftModal } from "@/components/draft/CreateDraftModal";
import { Sparkles, Plus, ArrowUpRight } from "lucide-react";
import { formatRelative, formatTime } from "@/lib/utils";
import { useState } from "react";
import { api } from "@/lib/api";

type Filter = "all" | "pending" | "approved" | "published" | "rejected";

const FILTERS: { label: string; value: Filter }[] = [
  { label: "All", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "Approved", value: "approved" },
  { label: "Published", value: "published" },
  { label: "Rejected", value: "rejected" },
];

export default function StudioPage() {
  const drafts = useDraftsLive();
  const [filter, setFilter] = useState<Filter>("all");
  const [draftModalOpen, setDraftModalOpen] = useState(false);

  const filtered = drafts.filter((d) => {
    if (filter === "all") return true;
    if (filter === "pending") return d.status === "pending_approval";
    if (filter === "approved") return d.status === "approved";
    if (filter === "published") return d.status === "published";
    if (filter === "rejected") return d.status === "rejected";
    return true;
  });

  function handleCreateDraft() {
    setDraftModalOpen(true);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Content Studio"
        title="Create and review drafts."
        description="Content Studio is for draft creation, review, versions, and publishing status. Research stays on the Research page."
        actions={
          <Button
            variant="primary"
            iconLeft={<Sparkles className="h-4 w-4" />}
            onClick={handleCreateDraft}
          >
            Create draft
          </Button>
        }
      />
      <CreateDraftModal open={draftModalOpen} onClose={() => setDraftModalOpen(false)} />

      {/* Filter rail */}
      <div className="flex items-center gap-1 border-b border-ink-600">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`relative px-3 py-2 text-[13px] transition-colors ${
              filter === f.value ? "text-ink-50" : "text-ink-200 hover:text-ink-50"
            }`}
          >
            {f.label}
            <span className="ml-2 font-mono text-2xs text-ink-300">
              {f.value === "all"
                ? drafts.length
                : drafts.filter((d) =>
                    f.value === "pending"
                      ? d.status === "pending_approval"
                      : f.value === "approved"
                        ? d.status === "approved"
                        : f.value === "published"
                          ? d.status === "published"
                          : d.status === "rejected",
                  ).length}
            </span>
            {filter === f.value && (
              <span className="absolute -bottom-px left-0 right-0 h-px bg-sodium-500" />
            )}
          </button>
        ))}
      </div>

      {/* List — editorial table */}
      <div className="rounded-lg border border-ink-600 overflow-hidden">
        <div className="grid grid-cols-12 gap-4 bg-ink-850 px-4 py-2.5 font-mono text-2xs uppercase tracking-wider text-ink-300 border-b border-ink-600">
          <div className="col-span-4">Post</div>
          <div className="col-span-1 text-center">Idea</div>
          <div className="col-span-2">Platform</div>
          <div className="col-span-1 text-center">Version</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-2 text-right">Updated</div>
        </div>
        <ul>
          {filtered.map((d) => (
            <li key={d.id} className="border-b border-ink-600 last:border-0">
              <Link
                href={`/studio/${d.id}`}
                className="grid grid-cols-12 gap-4 px-4 py-4 items-center hover:bg-ink-850/50 transition-colors group"
              >
                <div className="col-span-4 min-w-0">
                  <div className="text-sm text-ink-50 truncate">
                    {(d.caption ?? "").split("\n")[0]}
                  </div>
                  <div className="mt-1 font-mono text-2xs text-ink-300 truncate">
                    {d.format_label || d.strategy}
                  </div>
                </div>
                <div className="col-span-1 text-center">
                  {d.idea_index ? (
                    <Chip label={`#${d.idea_index}`} tone="sodium" />
                  ) : (
                    <span className="font-mono text-2xs text-ink-400">—</span>
                  )}
                </div>
                <div className="col-span-2">
                  <PlatformBadge platform={d.platform} />
                </div>
                <div className="col-span-1 text-center">
                  <Chip label={`v${d.version}`} tone="muted" />
                </div>
                <div className="col-span-2 flex items-center gap-2">
                  {d.metrics?.qa_status && (
                    <Chip 
                      label={`QA: ${d.metrics.qa_status}`} 
                      tone={
                        d.metrics.qa_status === "verified_pass" ? "positive" : 
                        d.metrics.qa_status === "content_passed" ? "neutral" : 
                        "critical"
                      } 
                    />
                  )}
                  <StatusDot
                    status={
                      d.status === "pending_approval"
                        ? "pending"
                        : d.status === "approved"
                          ? "approved"
                          : d.status === "published"
                            ? "published"
                            : d.status === "rejected"
                              ? "rejected"
                              : "draft"
                    }
                    withLabel
                  />
                </div>
                <div className="col-span-2 text-right">
                  <div className="font-mono text-xs text-ink-200 nums">{formatRelative(d.created_at)}</div>
                  {d.published_at && (
                    <div className="mt-0.5 font-mono text-2xs text-ink-300">
                      Live at {formatTime(d.published_at)}
                    </div>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
        {filtered.length === 0 && (
          <div className="px-4 py-12 text-center text-sm text-ink-200">No drafts in this filter.</div>
        )}
      </div>
    </div>
  );
}
