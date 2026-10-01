"use client";

import { useTimeline } from "@/lib/store";
import { AGENT_META, PIPELINE_STAGES, type AgentKind } from "@/lib/types";
import { cn, formatLatency } from "@/lib/utils";
import { Check, Loader2, Sparkle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/**
 * The signature component — streams actual agent work as it happens.
 * Each stage is more than a checkmark: it shows the agent, model, latency,
 * and a snippet of what the agent just produced. The spine is the product.
 */
export function AgentTimeline({ runId, dense = false }: { runId?: string; dense?: boolean }) {
  const events = useTimeline();
  const filtered = runId ? events.filter((e) => e.run_id === runId) : events.slice(-8);

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="relative inline-flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-sodium-500 animate-pulse-ring" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-sodium-500" />
          </span>
          <span className="font-mono text-2xs uppercase tracking-wider text-ink-200">Live · agent activity</span>
        </div>
        <span className="font-mono text-2xs text-ink-300">{filtered.length} events</span>
      </div>

      <ol className="relative">
        <span
          className="absolute left-[15px] top-2 bottom-2 w-px"
          style={{
            background:
              "linear-gradient(180deg, rgba(245,185,71,0.4) 0%, rgba(245,185,71,0.15) 60%, rgba(245,185,71,0) 100%)",
          }}
        />
        {filtered.map((ev, idx) => (
          <TimelineRow key={ev.id} event={ev} index={idx} dense={dense} />
        ))}
      </ol>
    </div>
  );
}

function TimelineRow({
  event,
  index,
  dense,
}: {
  event: ReturnType<typeof useTimeline>[number];
  index: number;
  dense?: boolean;
}) {
  const meta = AGENT_META[event.agent as AgentKind] ?? AGENT_META.research;
  const isRunning = event.status === "running";
  const isDone = event.status === "complete";

  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.04, ease: [0.16, 1, 0.3, 1] }}
      className="relative pl-10 pr-2 py-2.5"
    >
      <span
        className={cn(
          "absolute left-1 top-3 grid h-7 w-7 place-items-center rounded-full border bg-ink-900",
          isDone ? "border-sodium-500/60" : "border-sodium-500",
        )}
        style={{
          boxShadow: isRunning ? "0 0 16px rgba(245,185,71,0.35)" : "0 0 0 0 transparent",
        }}
      >
        {isDone ? (
          <Check className="h-3.5 w-3.5 text-sodium-500" strokeWidth={2.5} />
        ) : isRunning ? (
          <Loader2 className="h-3.5 w-3.5 text-sodium-500 animate-spin" />
        ) : (
          <span className="h-1.5 w-1.5 rounded-full bg-ink-400" />
        )}
      </span>

      <div className="flex items-baseline gap-2">
        <span className="text-sm font-medium text-ink-50">{event.label}</span>
        {event.model && event.model !== "—" && (
          <span className="font-mono text-2xs text-ink-300">{event.model}</span>
        )}
        {typeof event.latency_ms === "number" && (
          <span className="font-mono text-2xs text-ink-300">· {formatLatency(event.latency_ms)}</span>
        )}
        {isRunning && (
          <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-sodium-500">
            <span className="relative inline-flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-sodium-500 animate-pulse-ring" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-sodium-500" />
            </span>
            running
          </span>
        )}
      </div>
      {!dense && event.output_snippet && (
        <p className="mt-1 text-xs text-ink-200 leading-relaxed">
          <span className="text-ink-300">{">"}</span> {event.output_snippet}
        </p>
      )}
    </motion.li>
  );
}

/**
 * Compact horizontal pipeline-indicator — used on top of pages to show
 * current run position at a glance. Six checkpoints, sodium-amber lit
 * for completed, dim for pending.
 */
export function PipelineIndicator({ runId, className }: { runId?: string; className?: string }) {
  const events = useTimeline();
  const latest = runId ? events.filter((e) => e.run_id === runId) : events;

  const stages = PIPELINE_STAGES.slice(0, 6).map((stage) => {
    const ev = latest.find((e) => e.label === stage.label && e.status === "complete");
    return { stage, done: Boolean(ev) };
  });
  const lastIdx = stages.findIndex((s) => !s.done);

  return (
    <ol className={cn("flex items-center gap-1", className)}>
      {stages.map((s, i) => {
        const isDone = s.done;
        const isCurrent = i === lastIdx;
        return (
          <li key={s.stage.key} className="flex items-center gap-1">
            <span
              className={cn(
                "h-1.5 w-8 rounded-full transition-colors",
                isDone
                  ? "bg-sodium-500"
                  : isCurrent
                    ? "bg-sodium-500/40"
                    : "bg-ink-700",
              )}
            />
          </li>
        );
      })}
    </ol>
  );
}
