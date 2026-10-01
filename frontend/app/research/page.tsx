"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, ExternalLink, Lightbulb, Loader2, Search, TrendingUp, Users } from "lucide-react";
import { api } from "@/lib/api";
import { getStore, useInsightsLive } from "@/lib/store";
import type { ResearchInsight } from "@/lib/types";
import { formatRelative } from "@/lib/utils";
import { PageHeader } from "@/components/layout/PageHeader";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";

const FILTERS = [
  { label: "All", value: "all" },
  { label: "Industry", value: "industry" },
  { label: "Competitor", value: "competitor" },
  { label: "Trend", value: "trend" },
  { label: "Recommendation", value: "recommendation" },
] as const;

type Filter = (typeof FILTERS)[number]["value"];

export default function ResearchPage() {
  const insights = useInsightsLive();
  const [filter, setFilter] = useState<Filter>("all");
  const [topic, setTopic] = useState("");
  const [countryScope, setCountryScope] = useState<"global" | "india">("global");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filtered = insights.filter((i) => filter === "all" || i.source_kind === filter);
  const recommendations = insights.filter((i) => i.source_kind === "recommendation");
  const trends = insights.filter((i) => i.source_kind === "trend");
  const competitors = insights.filter((i) => i.source_kind === "competitor");
  const industries = insights.filter((i) => i.source_kind === "industry");
  const topSignal = useMemo(
    () => recommendations[0] ?? trends[0] ?? industries[0] ?? competitors[0],
    [competitors, industries, recommendations, trends],
  );

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .listResearch()
      .then((rows) => {
        if (alive) getStore().patch({ insights: rows });
      })
      .catch(() => {
        if (alive) setError("Could not load research insights.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function handleRunResearch() {
    setRunning(true);
    setError(null);
    const result = await api.runResearch(topic.trim() || undefined, countryScope);
    if (result?.insights) {
      getStore().patch({ insights: result.insights });
    } else {
      setError("Research run failed. Check the backend log and API keys.");
    }
    setRunning(false);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Research"
        title="Research only."
        description="Run industry, competitor, and trend discovery using the saved company profile as context. Content creation stays in Studio and Command Centre."
        actions={
          <div className="flex items-center gap-2">
            <div className="flex h-10 items-center overflow-hidden rounded-md border border-ink-600 bg-ink-850">
              {(["global", "india"] as const).map((scope) => (
                <button
                  key={scope}
                  type="button"
                  onClick={() => setCountryScope(scope)}
                  className={`h-full px-3 font-mono text-2xs uppercase tracking-wider transition-colors ${
                    countryScope === scope ? "bg-sodium-500 text-ink-950" : "text-ink-200 hover:text-ink-50"
                  }`}
                >
                  {scope}
                </button>
              ))}
            </div>
            <label className="relative flex h-10 w-72 max-w-[42vw] items-center gap-2 rounded-md border border-ink-600 bg-ink-850 px-3 text-sm text-ink-200 focus-within:border-ink-500">
              <Search className="h-3.5 w-3.5 text-ink-300" />
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Optional topic"
                className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-ink-300"
              />
            </label>
            <Button
              variant="primary"
              loading={running}
              iconLeft={running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              onClick={handleRunResearch}
            >
              {running ? "Researching" : "Run research"}
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-12 gap-px border border-ink-600 rounded-lg overflow-hidden bg-ink-600">
        <Pulse icon={<TrendingUp className="h-3.5 w-3.5" />} label="Industry" value={industries.length.toString()} sub="saved live insights" />
        <Pulse icon={<Users className="h-3.5 w-3.5" />} label="Competitors" value={competitors.length.toString()} sub="saved live insights" />
        <Pulse icon={<BarChart3 className="h-3.5 w-3.5" />} label="Trends" value={trends.length.toString()} sub="saved live insights" />
        <Pulse icon={<Lightbulb className="h-3.5 w-3.5" />} label="Recommendations" value={recommendations.length.toString()} sub="saved live insights" />
      </div>

      {error && <div className="rounded-md border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">{error}</div>}

      {topSignal && (
        <section className="rounded-xl border border-sodium-500/30 bg-ink-900 p-6">
          <div className="flex items-start gap-4">
            <span className="grid h-10 w-10 place-items-center rounded-md bg-sodium-500/15 text-sodium-500 border border-sodium-500/40">
              <Lightbulb className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <div className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Latest research signal</div>
              <h2 className="mt-1.5 font-display text-xl font-medium text-ink-50 text-balance">{topSignal.title}</h2>
              <p className="mt-2 text-sm text-ink-200 max-w-3xl leading-relaxed">{topSignal.summary}</p>
              {topSignal.url && (
                <a
                  href={topSignal.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-flex items-center gap-1.5 text-sm text-sodium-500 hover:text-sodium-400"
                >
                  Open source <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
            </div>
          </div>
        </section>
      )}

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
              {f.value === "all" ? insights.length : insights.filter((i) => i.source_kind === f.value).length}
            </span>
            {filter === f.value && <span className="absolute -bottom-px left-0 right-0 h-px bg-sodium-500" />}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {loading && <div className="col-span-full py-12 text-center text-sm text-ink-200">Loading research insights...</div>}
        {!loading && filtered.length === 0 && (
          <div className="col-span-full rounded-lg border border-dashed border-ink-600 bg-ink-900/40 p-10 text-center">
            <p className="text-sm text-ink-200">No research insights yet. Add the company profile, then run research.</p>
          </div>
        )}
        {filtered.map((ins, i) => (
          <motion.div
            key={ins.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.04, ease: [0.16, 1, 0.3, 1] }}
          >
            <InsightCard insight={ins} />
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function Pulse({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: string }) {
  return (
    <div className="col-span-6 md:col-span-3 bg-ink-900 px-4 py-3.5">
      <div className="flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-ink-300">
        {icon}
        {label}
      </div>
      <div className="mt-1 font-display text-base font-medium text-ink-50 nums">{value}</div>
      <div className="mt-0.5 text-xs text-ink-300">{sub}</div>
    </div>
  );
}

function InsightCard({ insight }: { insight: ResearchInsight }) {
  const tones = {
    trend: "sodium",
    industry: "steel",
    competitor: "muted",
    recommendation: "sodium",
  } as const;
  return (
    <article className="group rounded-xl border border-ink-600 bg-ink-900 p-5 hover:border-ink-500 transition-colors h-full flex flex-col">
      <div className="flex items-center justify-between">
        <Chip label={insight.source} tone={tones[insight.source_kind]} />
        <span className="font-mono text-2xs text-ink-300">{formatRelative(insight.captured_at)}</span>
      </div>
      <h3 className="mt-3 font-display text-base font-medium text-ink-50 leading-snug text-balance">{insight.title}</h3>
      <p className="mt-2 text-sm text-ink-200 leading-relaxed flex-1">{insight.summary}</p>
      <div className="mt-4 flex items-center gap-2 flex-wrap">
        {(insight.tags ?? []).map((t) => (
          <Chip key={t} label={t} tone="muted" />
        ))}
      </div>
      {insight.url && (
        <div className="mt-4 flex items-center gap-2 pt-4 border-t border-ink-600">
          <a href={insight.url} target="_blank" rel="noreferrer">
            <Button size="sm" variant="ghost" iconRight={<ExternalLink className="h-3.5 w-3.5" />}>
              Open source
            </Button>
          </a>
        </div>
      )}
    </article>
  );
}
