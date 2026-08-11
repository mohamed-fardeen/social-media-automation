"use client";

import { useInsights } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import { Sparkles, TrendingUp, Users, BarChart3, Lightbulb, ExternalLink } from "lucide-react";
import { formatRelative } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";
import type { ResearchInsight } from "@/lib/types";

const FILTERS = [
  { label: "All", value: "all" },
  { label: "Industry", value: "industry" },
  { label: "Competitor", value: "competitor" },
  { label: "Trend", value: "trend" },
  { label: "Recommendation", value: "recommendation" },
] as const;

type Filter = (typeof FILTERS)[number]["value"];

export default function ResearchPage() {
  const insights = useInsights();
  const [filter, setFilter] = useState<Filter>("all");

  const filtered = insights.filter((i) => filter === "all" || i.source_kind === filter);

  const recommendations = insights.filter((i) => i.source_kind === "recommendation");
  const trends = insights.filter((i) => i.source_kind === "trend");
  const competitors = insights.filter((i) => i.source_kind === "competitor");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Research"
        title="What the world is doing."
        description="The Research agent reads industry trends, monitors competitors, and surfaces recommendations. Convert any insight into a draft."
      />

      {/* Pulse bar */}
      <div className="grid grid-cols-12 gap-px border border-ink-600 rounded-lg overflow-hidden bg-ink-600">
        <Pulse icon={<TrendingUp className="h-3.5 w-3.5" />} label="Industries tracked" value="14" sub="3 changed this week" />
        <Pulse icon={<Users className="h-3.5 w-3.5" />} label="Competitors watched" value="7" sub="Linear + Height most active" />
        <Pulse icon={<BarChart3 className="h-3.5 w-3.5" />} label="Insights this week" value="48" sub="13 high-signal" />
        <Pulse icon={<Lightbulb className="h-3.5 w-3.5" />} label="Recommendations" value="6" sub="3 ready to convert" />
      </div>

      {/* AI recommendations hero */}
      <section className="rounded-xl border border-sodium-500/30 bg-gradient-to-br from-sodium-500/5 to-transparent p-6">
        <div className="flex items-start gap-4">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-sodium-500/15 text-sodium-500 border border-sodium-500/40">
            <Sparkles className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Strategic recommendation</div>
            <h2 className="mt-1.5 font-display text-xl font-medium text-ink-50 text-balance">
              Lead the next 4 weeks with "system of record" language.
            </h2>
            <p className="mt-2 text-sm text-ink-200 max-w-3xl leading-relaxed">
              Cross-correlating your top 90-day posts with audience reactions: posts that frame Atlas as a system of record
              outperform feature-led posts by 2.4x. We recommend reweighting the next 4-week content calendar toward this
              theme — and updating the strategist prompt to bias toward audit-trail and trust narratives.
            </p>
            <div className="mt-4 flex items-center gap-2">
              <Button variant="primary" iconLeft={<Sparkles className="h-3.5 w-3.5" />}>
                Generate 3 posts from this
              </Button>
              <Button variant="outline">Brief the editor</Button>
            </div>
          </div>
        </div>
      </section>

      {/* Filters */}
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

      {/* Insights grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
      <h3 className="mt-3 font-display text-base font-medium text-ink-50 leading-snug text-balance">
        {insight.title}
      </h3>
      <p className="mt-2 text-sm text-ink-200 leading-relaxed flex-1">{insight.summary}</p>
      <div className="mt-4 flex items-center gap-2 flex-wrap">
        {insight.tags.map((t) => (
          <Chip key={t} label={t} tone="muted" />
        ))}
      </div>
      <div className="mt-4 flex items-center gap-2 pt-4 border-t border-ink-600">
        <Button size="sm" variant="primary" iconLeft={<Sparkles className="h-3.5 w-3.5" />}>
          Generate content
        </Button>
        {insight.url && (
          <Button size="sm" variant="ghost" iconRight={<ExternalLink className="h-3.5 w-3.5" />}>
            Source
          </Button>
        )}
      </div>
    </article>
  );
}
