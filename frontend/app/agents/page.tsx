"use client";

import { useState } from "react";
import { useAgentLogs } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusDot } from "@/components/ui/StatusDot";
import { Chip } from "@/components/ui/Chip";
import { AGENT_META, type AgentKind } from "@/lib/types";
import { formatLatency, formatRelative, formatNumber } from "@/lib/utils";
import { Cpu, Search, Database, PenLine, Image as ImageIcon, Send, Brain, Filter } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const AGENT_ICONS: Record<AgentKind, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  research: Search,
  knowledge: Database,
  strategist: Brain,
  copywriter: PenLine,
  visual: ImageIcon,
  publisher: Send,
};

export default function AgentsPage() {
  const logs = useAgentLogs();
  const [open, setOpen] = useState<AgentKind | null>(null);

  const groups = (Object.keys(AGENT_META) as AgentKind[]).map((kind) => {
    const kindLogs = logs.filter((l) => l.agent === kind);
    const last = kindLogs[0];
    const running = kindLogs.find((l) => l.status === "running");
    return {
      kind,
      meta: AGENT_META[kind],
      last,
      running,
      count: kindLogs.length,
      totalLatency: kindLogs.reduce((s, l) => s + (l.latency_ms ?? 0), 0),
      totalTokens: kindLogs.reduce((s, l) => s + (l.tokens_in ?? 0) + (l.tokens_out ?? 0), 0),
    };
  });

  const selected = open ? groups.find((g) => g.kind === open) : null;
  const selectedLogs = open ? logs.filter((l) => l.agent === open) : [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Fleet"
        title="Six agents. One mission."
        description="Each agent is a specialized worker with a clear mandate. Click into one to see its recent runs, prompts, and outputs."
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left rail — agent list */}
        <ol className="col-span-12 lg:col-span-5 grid grid-cols-1 gap-px bg-ink-600 rounded-lg overflow-hidden border border-ink-600">
          {groups.map((g) => {
            const Icon = AGENT_ICONS[g.kind];
            const isOpen = open === g.kind;
            return (
              <li key={g.kind} className="bg-ink-900">
                <button
                  onClick={() => setOpen(isOpen ? null : g.kind)}
                  className={`group w-full text-left px-4 py-4 transition-colors ${isOpen ? "bg-ink-850" : "hover:bg-ink-850/50"}`}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className="grid h-9 w-9 shrink-0 place-items-center rounded-md border bg-ink-850"
                      style={{
                        borderColor: g.meta.color + "40",
                        background: `linear-gradient(180deg, ${g.meta.color}10, transparent)`,
                      }}
                    >
                      <Icon className="h-4 w-4 text-[color:var(--icon-color)]" style={{ "--icon-color": g.meta.color } as React.CSSProperties} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-ink-50">{g.meta.name}</span>
                        <span className="font-mono text-2xs text-ink-300">{g.meta.model}</span>
                        {g.running ? (
                          <StatusDot status="running" withLabel />
                        ) : g.last ? (
                          <StatusDot status="complete" withLabel />
                        ) : (
                          <StatusDot status="idle" withLabel />
                        )}
                      </div>
                      <p className="mt-1 text-xs text-ink-200">{g.meta.role}</p>
                      <div className="mt-2 flex items-center gap-3 font-mono text-2xs text-ink-300">
                        <span>{g.count} runs</span>
                        <span>·</span>
                        <span>{formatLatency(g.totalLatency)} total</span>
                        <span>·</span>
                        <span>{formatNumber(g.totalTokens)} tok</span>
                      </div>
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ol>

        {/* Right panel — current agent detail */}
        <aside className="col-span-12 lg:col-span-7 rounded-xl border border-ink-600 bg-ink-900 overflow-hidden">
          <AnimatePresence mode="wait">
            {selected ? (
              <motion.div
                key={selected.kind}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="divide-y divide-ink-600"
              >
                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span
                        className="grid h-10 w-10 place-items-center rounded-md border"
                        style={{
                          borderColor: selected.meta.color + "40",
                          background: `linear-gradient(180deg, ${selected.meta.color}10, transparent)`,
                        }}
                      >
                        {(() => {
                          const Icon = AGENT_ICONS[selected.kind];
                          return <Icon className="h-4.5 w-4.5 text-[color:var(--icon-color)]" style={{ "--icon-color": selected.meta.color } as React.CSSProperties} />;
                        })()}
                      </span>
                      <div>
                        <div className="text-base font-medium text-ink-50">{selected.meta.name}</div>
                        <div className="font-mono text-2xs text-ink-300">{selected.meta.model}</div>
                      </div>
                    </div>
                    {selected.running ? (
                      <StatusDot status="running" withLabel />
                    ) : (
                      <StatusDot status="complete" withLabel />
                    )}
                  </div>
                  <p className="mt-3 text-sm text-ink-200">{selected.meta.role}</p>

                  <div className="mt-5 grid grid-cols-3 gap-px bg-ink-600 rounded-lg overflow-hidden border border-ink-600">
                    <Stat label="Runs (recent)" value={selected.count.toString()} />
                    <Stat label="Latency" value={formatLatency(selected.totalLatency)} />
                    <Stat label="Tokens" value={formatNumber(selected.totalTokens)} />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between px-5 py-3">
                    <span className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Recent execution</span>
                    <Chip label={`${selectedLogs.length} entries`} tone="muted" />
                  </div>
                  <ol>
                    {selectedLogs.length === 0 && (
                      <li className="px-5 py-8 text-sm text-ink-200">No executions yet.</li>
                    )}
                    {selectedLogs.map((l) => (
                      <li key={l.id} className="px-5 py-3 border-t border-ink-600">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-2xs text-ink-300">{formatRelative(l.started_at)}</span>
                          <span className="font-mono text-2xs text-ink-400">run {l.run_id.slice(0, 12)}</span>
                          <StatusDot
                            status={l.status === "running" ? "running" : l.status === "complete" ? "complete" : "failed"}
                            withLabel
                          />
                          {typeof l.latency_ms === "number" && (
                            <span className="font-mono text-2xs text-ink-300 ml-auto">{formatLatency(l.latency_ms)}</span>
                          )}
                        </div>
                        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <div className="mono-label mb-1">Input</div>
                            <p className="text-sm text-ink-200 leading-relaxed">{l.input_summary ?? "—"}</p>
                          </div>
                          <div>
                            <div className="mono-label mb-1">Output</div>
                            <p className="text-sm text-ink-100 leading-relaxed">{l.output_summary ?? "—"}</p>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="h-full grid place-items-center text-center px-6 py-16"
              >
                <div>
                  <span className="grid h-10 w-10 mx-auto place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-200">
                    <Cpu className="h-4 w-4" />
                  </span>
                  <h3 className="mt-4 text-base font-medium text-ink-50">Select an agent</h3>
                  <p className="mt-1 max-w-sm text-sm text-ink-200">
                    Pick an agent on the left to inspect its recent runs, prompts, and outputs.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </aside>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ink-900 px-4 py-3">
      <div className="font-mono text-2xs uppercase tracking-wider text-ink-300">{label}</div>
      <div className="mt-1 font-display text-base font-medium text-ink-50 nums">{value}</div>
    </div>
  );
}
