"use client";

import { use, useState } from "react";
import { useDrafts, useApproveAction } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { PlatformBadge } from "@/components/ui/PlatformIcon";
import { StatusDot } from "@/components/ui/StatusDot";
import { Chip } from "@/components/ui/Chip";
import { AgentTimeline } from "@/components/timeline/AgentTimeline";
import { InstagramPreview } from "@/components/post-preview/InstagramPreview";
import { LinkedInPreview } from "@/components/post-preview/LinkedInPreview";
import { Check, RefreshCcw, X, ArrowLeft, History, MessageSquare } from "lucide-react";
import Link from "next/link";
import { formatRelative, formatTime } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

export default function StudioDraftPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const drafts = useDrafts();
  const action = useApproveAction();
  const [caption, setCaption] = useState<string | null>(null);
  const [hashtags, setHashtags] = useState<string[] | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [decided, setDecided] = useState<null | "approve" | "reject" | "regenerate">(null);

  const draft = drafts.find((d) => d.id === id);

  if (!draft) {
    return (
      <div className="rounded-lg border border-dashed border-ink-600 bg-ink-900/40 p-12 text-center">
        <p className="text-sm text-ink-200">Draft not found.</p>
        <Link href="/studio" className="mt-4 inline-flex items-center gap-1.5 text-sodium-500 text-sm">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to studio
        </Link>
      </div>
    );
  }

  const currentCaption = caption ?? draft.caption;
  const currentHashtags = hashtags ?? draft.hashtags;

  // Simulate prior versions — version history list
  const versions = Array.from({ length: draft.version }).map((_, i) => ({
    n: i + 1,
    label: i === draft.version - 1 ? "current" : i === 0 ? "first" : "iteration",
    ts: new Date(new Date(draft.created_at).getTime() - (draft.version - 1 - i) * 6_000_000).toISOString(),
    note: i === 0
      ? "Drafted by copywriter. Voice check passed."
      : i === 1
        ? "Tightened opening. Adjusted hook to 'trust metric'."
        : i === 2
          ? "Strategy refined after live engagement signal."
          : "Final pass.",
  }));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <Link
          href="/studio"
          className="inline-flex items-center gap-1.5 text-sm text-ink-200 hover:text-ink-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to studio
        </Link>
        <div className="flex items-center gap-2">
          <PlatformBadge platform={draft.platform} />
          <Chip label={`v${draft.version}`} tone="muted" />
          <StatusDot
            status={
              draft.status === "pending_approval"
                ? "pending"
                : draft.status === "approved"
                  ? "approved"
                  : draft.status === "published"
                    ? "published"
                    : draft.status === "rejected"
                      ? "rejected"
                      : "draft"
            }
            withLabel
          />
        </div>
      </div>

      <PageHeader
        eyebrow={`Studio / ${draft.platform}`}
        title="Draft editor"
        description="Edit the caption and hashtags — the live preview updates as you type. Submit feedback to ask the agents for a new version."
      />

      <div className="grid grid-cols-12 gap-8">
        {/* Editor */}
        <section className="col-span-12 lg:col-span-7 space-y-6">
          <div className="rounded-xl border border-ink-600 bg-ink-900 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Caption</span>
              <span className="font-mono text-2xs text-ink-300">{currentCaption.length} chars</span>
            </div>
            <textarea
              value={currentCaption}
              onChange={(e) => setCaption(e.target.value)}
              rows={14}
              className="w-full resize-none bg-transparent outline-none text-[15px] leading-relaxed text-ink-50"
            />
            <div className="hairline my-4" />
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Hashtags</span>
              {draft.platform === "linkedin" && (
                <span className="font-mono text-2xs text-ink-300">LinkedIn best: 0–3</span>
              )}
            </div>
            <input
              value={currentHashtags.join(" ")}
              onChange={(e) => setHashtags(e.target.value.split(/\s+/).filter(Boolean))}
              className="w-full bg-transparent outline-none text-[14px] font-mono text-ink-100 placeholder:text-ink-300"
              placeholder="#hashtag #another"
            />
          </div>

          {/* AI strategy / reasoning */}
          <div className="rounded-xl border border-ink-600 bg-ink-900 overflow-hidden">
            <div className="flex items-center justify-between border-b border-ink-600 px-5 py-3">
              <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Agent reasoning</span>
              <span className="font-mono text-2xs text-ink-300">grok-4 · strategist + copywriter</span>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <div className="mono-label mb-1.5">Strategy</div>
                <p className="text-sm text-ink-100 leading-relaxed">{draft.strategy}</p>
              </div>
              <div>
                <div className="mono-label mb-1.5">Reasoning</div>
                <p className="text-sm text-ink-200 leading-relaxed">{draft.reasoning}</p>
              </div>
              <div>
                <div className="mono-label mb-1.5">Image prompt</div>
                <p className="font-mono text-xs text-ink-200 leading-relaxed">{draft.image_prompt}</p>
              </div>
            </div>
          </div>

          {/* Version history */}
          <div className="rounded-xl border border-ink-600 bg-ink-900">
            <div className="flex items-center justify-between border-b border-ink-600 px-5 py-3">
              <div className="flex items-center gap-2">
                <History className="h-3.5 w-3.5 text-sodium-500" />
                <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Version history</span>
              </div>
              <span className="font-mono text-2xs text-ink-300">{versions.length} versions</span>
            </div>
            <ol>
              {versions.map((v) => (
                <li key={v.n} className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-ink-600 last:border-0 items-center">
                  <div className="col-span-1 font-mono text-sm text-ink-50">v{v.n}</div>
                  <div className="col-span-2 font-mono text-2xs text-ink-300">{v.label}</div>
                  <div className="col-span-7 text-sm text-ink-200">{v.note}</div>
                  <div className="col-span-2 text-right font-mono text-2xs text-ink-300">{formatRelative(v.ts)}</div>
                </li>
              ))}
            </ol>
          </div>

          {/* Actions */}
          <div className="rounded-xl border border-ink-600 bg-ink-900 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Decision</span>
              <span className="font-mono text-2xs text-ink-300">Operator: Abdullah K.</span>
            </div>
            <AnimatePresence mode="wait">
              {!decided && !showFeedback && (
                <motion.div key="a" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2">
                  <Button variant="primary" iconLeft={<Check className="h-3.5 w-3.5" />} onClick={() => { setDecided("approve"); action(draft.id, "approve"); }}>
                    Approve & publish
                  </Button>
                  <Button variant="outline" iconLeft={<RefreshCcw className="h-3.5 w-3.5" />} onClick={() => setShowFeedback(true)}>
                    Regenerate with feedback
                  </Button>
                  <Button variant="danger" iconLeft={<X className="h-3.5 w-3.5" />} onClick={() => { setDecided("reject"); action(draft.id, "reject"); }}>
                    Reject
                  </Button>
                </motion.div>
              )}
              {showFeedback && (
                <motion.div key="b" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-3.5 w-3.5 text-sodium-500" />
                    <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Feedback to the agents</span>
                  </div>
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    rows={4}
                    placeholder="Be specific. Reference the angle, the hook, the audience, or the image."
                    className="w-full rounded-md border border-ink-600 bg-ink-850 px-3 py-2 text-sm text-ink-50 placeholder:text-ink-300 outline-none focus:border-ink-500"
                  />
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      onClick={() => { setDecided("regenerate"); action(draft.id, "regenerate", feedback); setShowFeedback(false); }}
                    >
                      Send to agents
                    </Button>
                    <Button variant="ghost" onClick={() => setShowFeedback(false)}>Cancel</Button>
                  </div>
                </motion.div>
              )}
              {decided && (
                <motion.div key="c" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2 text-sm">
                  <StatusDot
                    status={decided === "approve" ? "approved" : decided === "reject" ? "rejected" : "running"}
                    withLabel
                  />
                  <span className="text-ink-200">
                    {decided === "approve" && "Approved. Publishing now."}
                    {decided === "reject" && "Rejected. This draft is locked."}
                    {decided === "regenerate" && "Feedback delivered. The agents are starting v" + (draft.version + 1) + "."}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </section>

        {/* Preview */}
        <aside className="col-span-12 lg:col-span-5 space-y-6">
          <div className="sticky top-24 space-y-6">
            <div className="rounded-xl border border-ink-600 bg-ink-900 p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Live preview</span>
                <span className="font-mono text-2xs text-ink-300">{draft.platform}</span>
              </div>
              {draft.platform === "instagram" ? (
                <InstagramPreview draft={{ ...draft, caption: currentCaption, hashtags: currentHashtags }} />
              ) : (
                <LinkedInPreview draft={{ ...draft, caption: currentCaption, hashtags: currentHashtags }} />
              )}
            </div>

            <div className="rounded-xl border border-ink-600 bg-ink-900 p-5">
              <div className="flex items-center justify-between mb-4">
                <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Live pipeline</span>
                <span className="font-mono text-2xs text-ink-300">run {draft.run_id.slice(0, 14)}</span>
              </div>
              <AgentTimeline runId={draft.run_id} dense />
            </div>

            <div className="rounded-xl border border-ink-600 bg-ink-900 p-5">
              <div className="mono-label mb-3">Schedule</div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-ink-50">
                    {draft.scheduled_for ? new Date(draft.scheduled_for).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                  </div>
                  <div className="font-mono text-2xs text-ink-300 mt-0.5">Optimal time for audience</div>
                </div>
                <Button variant="outline" size="sm">Reschedule</Button>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
