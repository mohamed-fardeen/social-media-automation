"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Check, Loader2, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { useDraftsLive, useRunsLive, refreshRuns, refreshDrafts } from "@/lib/store";

type Step = "source" | "topic" | "image_mode" | "ideas" | "draft" | "regen";

type Source = "research" | "user_topic";
type ImageMode = "text_only" | "with_image" | "mix";

interface Idea {
  index: number;
  angle: string;
  headline: string;
  summary: string;
  format?: string;
  format_label?: string;
  image_hint?: string;
}

interface CreateDraftModalProps {
  open: boolean;
  onClose: () => void;
}

export function CreateDraftModal({ open, onClose }: CreateDraftModalProps) {
  const [step, setStep] = useState<Step>("source");
  const [source, setSource] = useState<Source>("research");
  const [countryScope, setCountryScope] = useState<"global" | "india">("global");
  const [userTopic, setUserTopic] = useState("");
  const [imageMode, setImageMode] = useState<ImageMode>("with_image");
  const [runId, setRunId] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [regenFeedback, setRegenFeedback] = useState("");

  const runs = useRunsLive();
  const drafts = useDraftsLive();
  const liveRun = runs.find((r) => r.id === runId);
  const runDrafts = drafts.filter((d) => d.run_id === runId);

  // Once the run reaches awaiting_idea_selection, fetch ideas and advance.
  useEffect(() => {
    if (!runId || !liveRun) return;
    if (
      ideas.length === 0 &&
      (liveRun.status === "awaiting_idea_selection" || liveRun.status === "generating_drafts") &&
      Array.isArray(liveRun.ideas) && liveRun.ideas.length > 0
    ) {
      setIdeas(liveRun.ideas as Idea[]);
      setStep("ideas");
    }
  }, [runId, liveRun, ideas.length]);

  // Tight 2s poll while we're waiting for this specific run to arrive / update.
  // The global useRunsLive only polls every 10s which is too slow for the modal.
  useEffect(() => {
    if (!runId) return;
    // Stop polling once ideas are visible and drafts have arrived.
    if (ideas.length > 0 && runDrafts.length > 0) return;
    const timer = window.setInterval(async () => {
      await refreshRuns();
      await refreshDrafts();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [runId, ideas.length, runDrafts.length]);

  // Once drafts are saved for the selected ideas, advance to the draft step.
  useEffect(() => {
    if (!runId) return;
    if (step === "ideas" && runDrafts.length > 0) {
      setStep("draft");
    }
  }, [runId, runDrafts.length, step]);




  async function pickIdeas(indices: number[]) {
    if (!runId || indices.length === 0) return;
    setSelectedIndices(indices);
    setBusy(true);
    try {
      // Send selected indices as a single combined action (e.g. "1,2", "1,3", or "all")
      const choiceStr = indices.length === 3 ? "all" : indices.sort().join(",");
      await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"}/runs/${runId}/idea-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ choice: choiceStr, decided_by: "web_modal" }),
      });
    } catch {}
    // Move to generating state immediately — realtime will push drafts when ready.
    setStep("draft");
    setBusy(false);
  }

  async function approveDraft(draftId: string) {
    if (!runId) return;
    await api.approvalAction(runId, {
      draft_id: draftId,
      action: "approve",
      feedback: undefined,
      decided_by: "web_modal",
    });
  }

  async function regenerate(draftId: string, feedback: string) {
    if (!runId) return;
    setBusy(true);
    await api.regenerateWithFeedback(runId, feedback);
    setBusy(false);
    setRegenFeedback("");
    setStep("draft");
  }

  function close() {
    setStep("source");
    setSource("research");
    setCountryScope("global");
    setUserTopic("");
    setImageMode("with_image");
    setRunId(null);
    setIdeas([]);
    setSelectedIndices([]);
    setRegenFeedback("");
    onClose();
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="surface relative w-[min(560px,92vw)] max-h-[88vh] overflow-y-auto p-6"
      >
        <button
          onClick={close}
          className="absolute right-3 top-3 text-ink-300 hover:text-ink-50"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="mb-4 flex items-center gap-2 text-ink-200">
          <Sparkles className="h-4 w-4 text-sodium-500" />
          <span className="font-mono text-2xs uppercase tracking-wider">
            New draft — step{" "}
            {step === "source"
              ? "1"
              : step === "topic"
                ? "2"
                : step === "image_mode"
                  ? "3"
                  : step === "ideas"
                    ? "4"
                    : step === "draft"
                      ? "5"
                      : "6"}{" "}
            of 5
          </span>
        </div>

        <AnimatePresence mode="wait">
          {step === "source" && (
            <SourceStep
              countryScope={countryScope}
              onCountryScopeChange={setCountryScope}
              onPick={(s) => {
                setSource(s);
                if (s === "research") {
                  setStep("image_mode");
                } else {
                  setStep("topic");
                }
              }}
            />
          )}

          {step === "topic" && (
            <TopicStep
              value={userTopic}
              onChange={setUserTopic}
              onBack={() => setStep("source")}
              onNext={() => setStep("image_mode")}
            />
          )}

          {step === "image_mode" && (
            <ImageModeStep
              busy={busy}
              onPick={async (m) => {
                setImageMode(m);
                setBusy(true);
                try {
                  const res = await api.runDraft({
                    source,
                    user_topic: source === "user_topic" ? userTopic : undefined,
                    image_mode: m,
                    country_scope: countryScope,
                  });
                  const newRunId = res?.data?.run_id ?? null;
                  setRunId(newRunId);
                  if (newRunId) await refreshRuns();
                } catch {
                  // swallow — busy=false + no runId means user can retry
                }
                setBusy(false);
                setStep("ideas");
              }}
              onBack={() => setStep(source === "research" ? "source" : "topic")}
            />
          )}

          {step === "ideas" && (
            <IdeasStep
              ideas={ideas}
              busy={busy}
              onPick={(idxs) => pickIdeas(idxs)}
              onSkip={() => setStep("draft")}
            />
          )}

          {step === "draft" && (
            <DraftStep
              drafts={runDrafts}
              onApprove={approveDraft}
              onRegenerate={(draftId) => setStep("regen")}
              onDismiss={close}
            />
          )}

          {step === "regen" && (
            <RegenStep
              feedback={regenFeedback}
              onChange={setRegenFeedback}
              busy={busy}
              onBack={() => setStep("draft")}
              onSubmit={(fb) => {
                const draftId = runDrafts[0]?.id;
                if (draftId) regenerate(draftId, fb);
              }}
            />
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

function SourceStep({
  countryScope,
  onCountryScopeChange,
  onPick,
}: {
  countryScope: "global" | "india";
  onCountryScopeChange: (scope: "global" | "india") => void;
  onPick: (s: Source) => void;
}) {
  return (
    <motion.div key="source" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-lg text-ink-50">Where should I draw from?</h2>
          <p className="mt-1 text-sm text-ink-200">
            Choose whether to draw from recent research insights or specify your own topic idea.
          </p>
        </div>

        {/* Geographic Focus Toggle Pill */}
        <div className="flex shrink-0 h-9 items-center overflow-hidden rounded-md border border-ink-600 bg-ink-850 p-0.5">
          {(["global", "india"] as const).map((scope) => (
            <button
              key={scope}
              type="button"
              onClick={() => onCountryScopeChange(scope)}
              className={`h-full px-3 font-mono text-2xs uppercase tracking-wider rounded transition-colors ${
                countryScope === scope
                  ? "bg-sodium-500 text-ink-950 font-bold shadow-sm"
                  : "text-ink-300 hover:text-ink-50"
              }`}
            >
              {scope}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-3">
        <button
          onClick={() => onPick("research")}
          className="rounded-md border border-ink-600 bg-ink-900 px-4 py-3 text-left hover:border-sodium-500 transition-colors"
        >
          <div className="text-sm font-medium text-ink-50">
            Recent research ({countryScope.toUpperCase()})
          </div>
          <div className="text-xs text-ink-300">
            Use the most recent insights from our {countryScope === "india" ? "Indian" : "global"} research table.
          </div>
        </button>
        <button
          onClick={() => onPick("user_topic")}
          className="rounded-md border border-ink-600 bg-ink-900 px-4 py-3 text-left hover:border-sodium-500 transition-colors"
        >
          <div className="text-sm font-medium text-ink-50">Your own idea</div>
          <div className="text-xs text-ink-300">
            Tell me what you want to post about. I'll weave in brand context and {countryScope.toUpperCase()} research.
          </div>
        </button>
      </div>
    </motion.div>
  );
}

function TopicStep({
  value,
  onChange,
  onBack,
  onNext,
}: {
  value: string;
  onChange: (v: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <motion.div key="topic" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <h2 className="font-display text-lg text-ink-50">What should the post be about?</h2>
      <p className="mt-1 text-sm text-ink-200">
        Type a topic in one sentence. We'll pull related research and brand knowledge.
      </p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder="e.g. AI safety in commercial real estate"
        className="mt-4 w-full rounded-md border border-ink-600 bg-ink-900 p-3 text-sm text-ink-50 placeholder:text-ink-400 outline-none focus:border-sodium-500"
      />
      <div className="mt-4 flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs text-ink-300 hover:text-ink-50"
        >
          <ArrowLeft className="h-3 w-3" />
          Back
        </button>
        <button
          onClick={onNext}
          disabled={!value.trim()}
          className="rounded-md bg-sodium-500 px-3 py-1.5 text-sm font-medium text-ink-950 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </motion.div>
  );
}

function ImageModeStep({
  onPick,
  onBack,
  busy,
}: {
  onPick: (m: ImageMode) => void;
  onBack: () => void;
  busy?: boolean;
}) {
  return (
    <motion.div key="image_mode" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <h2 className="font-display text-lg text-ink-50">Text-only, with image, or mix?</h2>
      <p className="mt-1 text-sm text-ink-200">
        Text-only skips image generation. With image generates a hero image for every idea.
        Mix gives you at least one of each.
      </p>
      <div className="mt-5 grid gap-3">
        {[
          { v: "text_only", t: "Text only", d: "Caption only — no image generation." },
          { v: "with_image", t: "With image", d: "Every idea gets a generated image." },
          { v: "mix", t: "Mix", d: "At least one text-only + one with image." },
        ].map((opt) => (
          <button
            key={opt.v}
            onClick={() => onPick(opt.v as ImageMode)}
            disabled={busy}
            className="rounded-md border border-ink-600 bg-ink-900 px-4 py-3 text-left hover:border-sodium-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="text-sm font-medium text-ink-50">{opt.t}</div>
            <div className="text-xs text-ink-300">{opt.d}</div>
          </button>
        ))}
      </div>
      <div className="mt-4">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs text-ink-300 hover:text-ink-50"
        >
          <ArrowLeft className="h-3 w-3" />
          Back
        </button>
      </div>
    </motion.div>
  );
}

function IdeasStep({
  ideas,
  busy,
  onPick,
  onSkip,
}: {
  ideas: Idea[];
  busy: boolean;
  onPick: (idxs: number[]) => void;
  onSkip: () => void;
}) {
  const [selected, setSelected] = useState<number[]>([1]); // default pick idea 1

  const toggleIdea = (index: number) => {
    setSelected((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const selectAll = () => {
    if (selected.length === ideas.length) {
      setSelected([]);
    } else {
      setSelected(ideas.map((i) => i.index));
    }
  };

  if (ideas.length === 0) {
    return (
      <div className="grid place-items-center py-12 text-sm text-ink-200">
        <Loader2 className="h-5 w-5 animate-spin text-sodium-500" />
        <span className="mt-3">Generating 3 ideas from your context…</span>
      </div>
    );
  }

  return (
    <motion.div key="ideas" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg text-ink-50">Select Ideas to Develop</h2>
          <p className="text-xs text-ink-300">Click to select one or multiple ideas for draft generation.</p>
        </div>
        <button
          type="button"
          onClick={selectAll}
          className="text-xs font-mono text-sodium-400 hover:text-sodium-300 transition-colors"
        >
          {selected.length === ideas.length ? "Deselect All" : "Select All"}
        </button>
      </div>

      <div className="mt-4 space-y-3">
        {ideas.map((idea) => {
          const isSelected = selected.includes(idea.index);
          return (
            <button
              key={idea.index}
              type="button"
              onClick={() => toggleIdea(idea.index)}
              className={`w-full text-left transition-all rounded-lg border p-3.5 relative cursor-pointer ${
                isSelected
                  ? "border-sodium-500 bg-sodium-500/10 shadow-[0_0_15px_rgba(245,158,11,0.08)] ring-1 ring-sodium-500/40"
                  : "border-ink-700/80 bg-ink-900/90 hover:border-ink-500 hover:bg-ink-850"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-2xs uppercase tracking-wider text-ink-400">
                    Idea {idea.index}
                  </span>
                  {idea.format_label && (
                    <span className="rounded bg-ink-800 border border-ink-700 px-1.5 py-0.5 text-2xs uppercase tracking-wider text-ink-200 font-medium">
                      {idea.format_label}
                    </span>
                  )}
                  {idea.image_hint && (
                    <span className="rounded bg-sodium-500/20 border border-sodium-500/30 px-1.5 py-0.5 text-2xs uppercase tracking-wider text-sodium-400 font-medium">
                      with image
                    </span>
                  )}
                </div>

                <div
                  className={`h-5 w-5 rounded-md border flex items-center justify-center shrink-0 transition-colors ${
                    isSelected
                      ? "border-sodium-500 bg-sodium-500 text-ink-950"
                      : "border-ink-600 bg-ink-950 text-transparent"
                  }`}
                >
                  <Check className="h-3.5 w-3.5 stroke-[3]" />
                </div>
              </div>

              <div className="mt-2 text-sm font-semibold text-ink-50 leading-snug">
                {idea.headline}
              </div>
              <div className="mt-1 text-xs text-ink-300 leading-relaxed">
                {idea.summary}
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-6 flex items-center justify-between pt-3 border-t border-ink-800">
        <span className="text-xs text-ink-400">
          {selected.length === 0
            ? "No ideas selected"
            : `${selected.length} of ${ideas.length} selected`}
        </span>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSkip}
            disabled={busy}
            className="rounded-md border border-ink-700 px-3 py-1.5 text-xs text-ink-300 hover:text-ink-100 hover:border-ink-500 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onPick(selected)}
            disabled={busy || selected.length === 0}
            className="inline-flex items-center gap-1.5 rounded-md bg-sodium-500 px-4 py-1.5 text-xs font-semibold text-ink-950 transition-all hover:bg-sodium-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            {busy ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Generating...
              </>
            ) : (
              `Proceed ${selected.length > 0 ? `(${selected.length})` : ""}`
            )}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function DraftStep({
  drafts,
  onApprove,
  onRegenerate,
  onDismiss,
}: {
  drafts: any[];
  onApprove: (id: string) => void;
  onRegenerate: (id: string) => void;
  onDismiss: () => void;
}) {
  if (drafts.length === 0) {
    return (
      <div className="grid place-items-center py-12 text-sm text-ink-200">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="mt-3">Drafting your post…</span>
      </div>
    );
  }
  return (
    <motion.div key="draft" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <h2 className="font-display text-lg text-ink-50">Here&apos;s the draft{drafts.length > 1 ? "s" : ""}</h2>
      <div className="mt-4 space-y-4">
        {drafts.map((d) => (
          <div key={d.id} className="rounded-md border border-ink-600 bg-ink-900 p-4">
            {d.image_url && (
              <img
                src={d.image_url}
                alt=""
                className="mb-3 h-40 w-full rounded object-cover"
              />
            )}
            <div className="text-sm text-ink-50 whitespace-pre-wrap">
              {d.caption || "(no caption)"}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={() => onApprove(d.id)}
                className="rounded-md bg-live-ok/20 px-3 py-1.5 text-xs text-live-ok hover:bg-live-ok/30"
              >
                Approve
              </button>
              <button
                onClick={() => onRegenerate(d.id)}
                className="rounded-md border border-ink-600 px-3 py-1.5 text-xs text-ink-200 hover:text-ink-50"
              >
                Regenerate
              </button>
              <button
                onClick={onDismiss}
                className="rounded-md border border-ink-600 px-3 py-1.5 text-xs text-ink-200 hover:text-ink-50"
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

function RegenStep({
  feedback,
  onChange,
  busy,
  onBack,
  onSubmit,
}: {
  feedback: string;
  onChange: (v: string) => void;
  busy: boolean;
  onBack: () => void;
  onSubmit: (v: string) => void;
}) {
  return (
    <motion.div key="regen" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <h2 className="font-display text-lg text-ink-50">What should change?</h2>
      <p className="mt-1 text-sm text-ink-200">
        Describe the change in your own words. Examples: "make the headline punchier",
        "drop the second bullet", "lead with the cost-saving stat".
      </p>
      <textarea
        value={feedback}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        placeholder="What should change?"
        className="mt-4 w-full rounded-md border border-ink-600 bg-ink-900 p-3 text-sm text-ink-50 placeholder:text-ink-400 outline-none focus:border-sodium-500"
      />
      <div className="mt-4 flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs text-ink-300 hover:text-ink-50"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to draft
        </button>
        <button
          onClick={() => onSubmit(feedback)}
          disabled={!feedback.trim() || busy}
          className="rounded-md bg-sodium-500 px-3 py-1.5 text-sm font-medium text-ink-950 disabled:opacity-40"
        >
          {busy ? "Regenerating…" : "Regenerate"}
        </button>
      </div>
    </motion.div>
  );
}
