"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Check, Loader2, Sparkles, X, Globe, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useDraftsLive, useRunsLive, refreshRuns, refreshDrafts } from "@/lib/store";

type Step = "scope" | "topic" | "image_mode" | "researching" | "ideas" | "draft" | "regen";
type Scope = "scan" | "topic";
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

interface RunCampaignModalProps {
  open: boolean;
  onClose: () => void;
  brandId?: string;
}

export function RunCampaignModal({ open, onClose, brandId }: RunCampaignModalProps) {
  const [step, setStep] = useState<Step>("scope");
  const [scope, setScope] = useState<Scope>("scan");
  const [countryScope, setCountryScope] = useState<"global" | "india">("global");
  const [userTopic, setUserTopic] = useState("");
  const [imageMode, setImageMode] = useState<ImageMode>("with_image");
  const [runId, setRunId] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([1]);
  const [busy, setBusy] = useState(false);
  const [regenFeedback, setRegenFeedback] = useState("");

  const runs = useRunsLive();
  const drafts = useDraftsLive();
  const liveRun = runs.find((r) => r.id === runId);
  const runDrafts = drafts.filter((d) => d.run_id === runId);

  // When run is in researching/strategizing, watch for ideas
  useEffect(() => {
    if (!runId || !liveRun) return;
    if (
      ideas.length === 0 &&
      (liveRun.status === "awaiting_idea_selection" || liveRun.status === "generating_drafts") &&
      Array.isArray(liveRun.ideas) &&
      liveRun.ideas.length > 0
    ) {
      setIdeas(liveRun.ideas as Idea[]);
      setStep("ideas");
    }
  }, [runId, liveRun, ideas.length]);

  // Fast 2s poll while waiting for research, ideas, and drafts to complete
  useEffect(() => {
    if (!runId) return;
    if (ideas.length > 0 && runDrafts.length > 0) return;
    const timer = window.setInterval(async () => {
      await refreshRuns();
      await refreshDrafts();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [runId, ideas.length, runDrafts.length]);

  // Once drafts are saved for the selected ideas, advance to the draft step
  useEffect(() => {
    if (!runId) return;
    if (step === "ideas" && runDrafts.length > 0) {
      setStep("draft");
    }
  }, [runId, runDrafts.length, step]);

  async function handleStartCampaign(mode: ImageMode) {
    setImageMode(mode);
    setBusy(true);
    setStep("researching");
    try {
      const res = await api.runNow({
        brand_id: brandId,
        mode: "full_pipeline",
        image_mode: mode,
        source_mode: scope === "topic" ? "user_topic" : "research",
        topic: scope === "topic" ? userTopic : undefined,
        user_topic: scope === "topic" ? userTopic : undefined,
        country_scope: countryScope,
        trigger: "web_modal",
      });
      const newRunId = res?.data?.run_id ?? null;
      setRunId(newRunId);
      if (newRunId) await refreshRuns();
    } catch {
      // allow retry
    }
    setBusy(false);
  }

  async function pickIdeas(indices: number[]) {
    if (!runId || indices.length === 0) return;
    setSelectedIndices(indices);
    setBusy(true);
    try {
      const choiceStr = indices.length === 3 ? "all" : indices.sort().join(",");
      await api.pickIdeas(runId, choiceStr, "web_modal");
    } catch {}
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
    setStep("scope");
    setScope("scan");
    setUserTopic("");
    setImageMode("with_image");
    setRunId(null);
    setIdeas([]);
    setSelectedIndices([1]);
    setRegenFeedback("");
    onClose();
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="surface relative w-[min(580px,92vw)] max-h-[88vh] overflow-y-auto p-6"
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
            Run full campaign —{" "}
            {step === "scope"
              ? "1. Research Scope"
              : step === "topic"
                ? "2. Topic Focus"
                : step === "image_mode"
                  ? "3. Visual Format"
                  : step === "researching"
                    ? "4. Research & Strategy"
                    : step === "ideas"
                      ? "4. Idea Selection"
                      : step === "draft"
                        ? "5. Draft Preview"
                        : "Regenerate"}
          </span>
        </div>

        <AnimatePresence mode="wait">
          {step === "scope" && (
            <ScopeStep
              countryScope={countryScope}
              onCountryScopeChange={setCountryScope}
              onPick={(s) => {
                setScope(s);
                if (s === "scan") {
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
              onBack={() => setStep("scope")}
              onNext={() => setStep("image_mode")}
            />
          )}

          {step === "image_mode" && (
            <ImageModeStep
              busy={busy}
              onPick={handleStartCampaign}
              onBack={() => setStep(scope === "scan" ? "scope" : "topic")}
            />
          )}

          {step === "researching" && (
            <ResearchingStep liveRun={liveRun} />
          )}

          {step === "ideas" && (
            <IdeasStep
              ideas={ideas}
              busy={busy}
              onPick={pickIdeas}
              onSkip={() => setStep("draft")}
            />
          )}

          {step === "draft" && (
            <DraftStep
              drafts={runDrafts}
              onApprove={approveDraft}
              onRegenerate={() => setStep("regen")}
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

function ScopeStep({
  countryScope,
  onCountryScopeChange,
  onPick,
}: {
  countryScope: "global" | "india";
  onCountryScopeChange: (scope: "global" | "india") => void;
  onPick: (s: Scope) => void;
}) {
  return (
    <motion.div key="scope" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-lg text-ink-50">Choose Campaign Research Scope</h2>
          <p className="mt-1 text-sm text-ink-200">
            The full campaign triggers a fresh autonomous research pass. Choose your geographic focus and research scope.
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
          onClick={() => onPick("scan")}
          className="group rounded-lg border border-ink-600 bg-ink-900/90 p-4 text-left transition-all hover:border-sodium-500 hover:bg-ink-850"
        >
          <div className="flex items-center gap-2.5">
            <Globe className="h-4 w-4 text-sodium-500" />
            <div className="text-sm font-medium text-ink-50">
              Automated Industry & Competitor Scan ({countryScope.toUpperCase()})
            </div>
          </div>
          <div className="mt-1.5 text-xs text-ink-300 leading-relaxed">
            Performs live Google, Tavily & social searches for novel breakthroughs, competitor projects, and technical updates in robotic 3D concrete printing {countryScope === "india" ? "across India and regional hubs" : "worldwide"}.
          </div>
        </button>
        <button
          onClick={() => onPick("topic")}
          className="group rounded-lg border border-ink-600 bg-ink-900/90 p-4 text-left transition-all hover:border-sodium-500 hover:bg-ink-850"
        >
          <div className="flex items-center gap-2.5">
            <Search className="h-4 w-4 text-steel-500" />
            <div className="text-sm font-medium text-ink-50">Research a Specific Topic or Angle</div>
          </div>
          <div className="mt-1.5 text-xs text-ink-300 leading-relaxed">
            Specify a custom subject (e.g. material durability, polar vs gantry, MES project). The research agent will conduct targeted online extraction on that topic with {countryScope.toUpperCase()} priority.
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
      <h2 className="font-display text-lg text-ink-50">What topic should we research?</h2>
      <p className="mt-1 text-sm text-ink-200">
        Enter the focus topic. Our research agent will plan search queries, scrape verified web evidence, and feed the findings into the strategist.
      </p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder="e.g. Seismic performance and structural codes for 3D printed concrete walls"
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
          className="rounded-md bg-sodium-500 px-3.5 py-1.5 text-sm font-medium text-ink-950 disabled:opacity-40"
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
      <h2 className="font-display text-lg text-ink-50">Visual & Image Preferences</h2>
      <p className="mt-1 text-sm text-ink-200">
        Configure how visual assets should be generated for the ideas in this campaign.
      </p>
      <div className="mt-5 grid gap-3">
        {[
          { v: "with_image", t: "With image", d: "Generate photorealistic architectural / robotic hero visuals for each idea." },
          { v: "text_only", t: "Text only", d: "High-impact editorial captions only — skips image generation entirely." },
          { v: "mix", t: "Mix", d: "At least one text-focused idea and image-backed ideas to choose from." },
        ].map((opt) => (
          <button
            key={opt.v}
            onClick={() => onPick(opt.v as ImageMode)}
            disabled={busy}
            className="rounded-lg border border-ink-600 bg-ink-900/90 px-4 py-3 text-left transition-all hover:border-sodium-500 hover:bg-ink-850 disabled:opacity-50"
          >
            <div className="text-sm font-medium text-ink-50">{opt.t}</div>
            <div className="mt-0.5 text-xs text-ink-300">{opt.d}</div>
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

function ResearchingStep({ liveRun }: { liveRun?: any }) {
  const currentAgent = liveRun?.current_agent || liveRun?.status || "research";

  return (
    <motion.div key="researching" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="py-8 text-center space-y-6">
      <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-sodium-500/10 border border-sodium-500/30">
        <Loader2 className="h-7 w-7 animate-spin text-sodium-500" />
      </div>

      <div className="space-y-2">
        <h2 className="font-display text-lg text-ink-50">Conducting Fresh Research & Intelligence Scan</h2>
        <p className="text-xs text-ink-300 max-w-md mx-auto">
          The agent swarm is executing Google / Tavily search queries, crawling verified engineering sources, cross-referencing brand knowledge, and formulating 3 candidate angles.
        </p>
      </div>

      <div className="mx-auto max-w-xs rounded-md border border-ink-700 bg-ink-900/80 p-3 text-left space-y-2 font-mono text-2xs">
        <div className="flex items-center justify-between">
          <span className="text-ink-400">Current Phase:</span>
          <span className="uppercase text-sodium-400 font-semibold">{currentAgent}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-ink-400">Pipeline:</span>
          <span className="text-ink-200">Research → RAG → Strategy → 3 Ideas</span>
        </div>
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
  const [selected, setSelected] = useState<number[]>([1]);

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
        <span className="mt-3">Synthesizing 3 candidate ideas from fresh research…</span>
      </div>
    );
  }

  return (
    <motion.div key="ideas" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg text-ink-50">Select Ideas to Develop</h2>
          <p className="text-xs text-ink-300">Choose one or more ideas to turn into published-ready drafts.</p>
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
                  {idea.image_hint ? (
                    <span className="rounded bg-sodium-500/20 border border-sodium-500/30 px-1.5 py-0.5 text-2xs uppercase tracking-wider text-sodium-400 font-medium">
                      with image
                    </span>
                  ) : (
                    <span className="rounded bg-ink-800 border border-ink-700 px-1.5 py-0.5 text-2xs uppercase tracking-wider text-ink-400">
                      text only
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
            Close
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
              `Generate Drafts ${selected.length > 0 ? `(${selected.length})` : ""}`
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
        <Loader2 className="h-5 w-5 animate-spin text-sodium-500" />
        <span className="mt-3">Drafting copy & generating visuals…</span>
      </div>
    );
  }
  return (
    <motion.div key="draft" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <h2 className="font-display text-lg text-ink-50">Campaign Draft{drafts.length > 1 ? "s" : ""} Ready</h2>
      <div className="mt-4 space-y-4 max-h-[50vh] overflow-y-auto pr-1">
        {drafts.map((d) => (
          <div key={d.id} className="rounded-lg border border-ink-600 bg-ink-900 p-4">
            {d.image_url && (
              <img
                src={d.image_url}
                alt=""
                className="mb-3 h-44 w-full rounded object-cover"
              />
            )}
            <div className="text-sm text-ink-50 whitespace-pre-wrap">
              {d.caption || "(no caption)"}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={() => onApprove(d.id)}
                className="rounded-md bg-live-ok/20 px-3 py-1.5 text-xs font-medium text-live-ok hover:bg-live-ok/30"
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
                Done
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
      <h2 className="font-display text-lg text-ink-50">Regeneration Feedback</h2>
      <p className="mt-1 text-sm text-ink-200">
        Describe how to refine the copy or visuals (e.g. &quot;make hook more technical&quot;, &quot;emphasize polar printer advantage&quot;).
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
          className="rounded-md bg-sodium-500 px-3.5 py-1.5 text-sm font-medium text-ink-950 disabled:opacity-40"
        >
          {busy ? "Regenerating…" : "Regenerate"}
        </button>
      </div>
    </motion.div>
  );
}
