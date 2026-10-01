"use client";

import { useDrafts } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlatformBadge } from "@/components/ui/PlatformIcon";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import { formatNumber, formatRelative } from "@/lib/utils";
import { useMemo } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { ArrowUpRight, TrendingUp, Eye, Heart, MessageCircle, Repeat, Download } from "lucide-react";

export default function AnalyticsPage() {
  const drafts = useDrafts();

  const published = useMemo(() => drafts.filter((d) => d.status === "published" && d.metrics), [drafts]);

  const stats = useMemo(() => {
    const totalPosts = drafts.length;
    const approved = drafts.filter((d) => d.status === "approved" || d.status === "published").length;
    const rejected = drafts.filter((d) => d.status === "rejected").length;
    const totalEngagement = published.reduce((s, d) => {
      const m = d.metrics!;
      return s + (m.likes ?? 0) + (m.comments ?? 0) + (m.shares ?? 0);
    }, 0);
    const totalImpressions = published.reduce((s, d) => s + (d.metrics?.impressions ?? 0), 0);
    return {
      totalPosts,
      approved,
      rejected,
      totalEngagement,
      totalImpressions,
      approvalRate: totalPosts ? Math.round((approved / totalPosts) * 100) : 0,
      regenRate: totalPosts ? Math.round((rejected / totalPosts) * 100) : 0,
    };
  }, [drafts, published]);

  // Engagement over time (last 14 days)
  const series = useMemo(() => {
    const days = Array.from({ length: 14 }, (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - (13 - i));
      const key = date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      return { day: key, engagement: 0, impressions: 0, ig: 0, li: 0 };
    });
    return days;
  }, []);

  // Reach per post horizontal bar
  const postReach = useMemo(
    () =>
      published
        .slice()
        .sort((a, b) => (b.metrics?.impressions ?? 0) - (a.metrics?.impressions ?? 0))
        .slice(0, 6)
        .map((d) => ({
          id: d.id,
          label: d.caption.split("\n")[0].slice(0, 60),
          reach: d.metrics?.impressions ?? 0,
          platform: d.platform,
        })),
    [published],
  );

  // Platform split
  const platformSplit = useMemo(() => {
    const ig = published.filter((d) => d.platform === "instagram").reduce((s, d) => s + (d.metrics?.impressions ?? 0), 0);
    const li = published.filter((d) => d.platform === "linkedin").reduce((s, d) => s + (d.metrics?.impressions ?? 0), 0);
    return [
      { name: "Instagram", value: ig, color: "#F472A4" },
      { name: "LinkedIn", value: li, color: "#7BB6F8" },
    ];
  }, [published]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Analytics"
        title="Did it land?"
        description="Engagement, approval rhythm, and platform by platform. Numbers update as the publisher posts."
        actions={
          <Button variant="outline" iconLeft={<Download className="h-3.5 w-3.5" />}>
            Export CSV
          </Button>
        }
      />

      {/* Top stats — single editorial row */}
      <div className="grid grid-cols-12 gap-px bg-ink-600 border border-ink-600 rounded-lg overflow-hidden">
        <Stat label="Posts generated" value={stats.totalPosts.toString()} sub="all time" />
        <Stat label="Approval rate" value={`${stats.approvalRate}%`} sub="human-decided" />
        <Stat label="Regen rate" value={`${stats.regenRate}%`} sub="sent back to agents" />
        <Stat label="Engagement" value={formatNumber(stats.totalEngagement)} sub="likes, comments, shares" />
        <Stat label="Impressions" value={formatNumber(stats.totalImpressions)} sub="platform-wide" />
        <Stat label="Velocity" value="2.1d" sub="avg cycle time" />
      </div>

      {/* Engagement over time */}
      <div className="rounded-xl border border-ink-600 bg-ink-900 p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <div className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Engagement</div>
            <h2 className="mt-1 font-display text-lg font-medium text-ink-50">Last 14 days</h2>
          </div>
          <div className="flex items-center gap-2">
            <Chip label="Aggregate" tone="sodium" />
            <span className="font-mono text-2xs text-ink-300">All platforms</span>
          </div>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ top: 8, right: 0, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="eng" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F5B947" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#F5B947" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#23252B" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="day" stroke="#5A5D65" fontSize={10} tickLine={false} axisLine={false} />
              <YAxis stroke="#5A5D65" fontSize={10} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: "#131417",
                  border: "1px solid #2E3038",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#EDEEF0",
                }}
                cursor={{ stroke: "#F5B947", strokeWidth: 1, strokeDasharray: "2 2" }}
              />
              <Area
                type="monotone"
                dataKey="engagement"
                stroke="#F5B947"
                strokeWidth={1.5}
                fill="url(#eng)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Two-col: platform split + top posts */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-5 rounded-xl border border-ink-600 bg-ink-900 p-6">
          <div className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Reach</div>
          <h2 className="mt-1 font-display text-lg font-medium text-ink-50">By platform</h2>
          <div className="mt-6 space-y-4">
            {platformSplit.map((p) => {
              const total = platformSplit.reduce((s, x) => s + x.value, 0) || 1;
              const pct = Math.round((p.value / total) * 100);
              return (
                <div key={p.name}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-ink-100">{p.name}</span>
                    <span className="font-mono text-ink-300 nums">{formatNumber(p.value)} · {pct}%</span>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-ink-700 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: p.color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7 rounded-xl border border-ink-600 bg-ink-900 p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="font-mono text-2xs uppercase tracking-wider text-sodium-500">Top posts</div>
              <h2 className="mt-1 font-display text-lg font-medium text-ink-50">By reach</h2>
            </div>
          </div>
          <ul className="space-y-3">
            {postReach.map((p, i) => (
              <li key={p.id} className="grid grid-cols-12 gap-3 items-center">
                <div className="col-span-1 font-mono text-2xs text-ink-300">0{i + 1}</div>
                <div className="col-span-1"><PlatformBadge platform={p.platform as any} /></div>
                <div className="col-span-7 text-sm text-ink-100 truncate">{p.label}</div>
                <div className="col-span-3 text-right">
                  <div className="font-mono text-xs text-ink-50 nums">{formatNumber(p.reach)}</div>
                  <div className="mt-0.5 h-1 rounded-full bg-ink-700 overflow-hidden">
                    <div
                      className="h-full bg-sodium-500"
                      style={{ width: `${Math.min(100, (p.reach / (postReach[0]?.reach ?? 1)) * 100)}%` }}
                    />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Recent post performance table */}
      <div className="rounded-xl border border-ink-600 overflow-hidden">
        <div className="grid grid-cols-12 bg-ink-850 px-4 py-2.5 font-mono text-2xs uppercase tracking-wider text-ink-300 border-b border-ink-600">
          <div className="col-span-5">Post</div>
          <div className="col-span-1">Platform</div>
          <div className="col-span-2 text-right">Impressions</div>
          <div className="col-span-1 text-right">Likes</div>
          <div className="col-span-1 text-right">Comments</div>
          <div className="col-span-1 text-right">Shares</div>
          <div className="col-span-1 text-right">Published</div>
        </div>
        {published.map((d) => (
          <div key={d.id} className="grid grid-cols-12 gap-3 px-4 py-3.5 border-b border-ink-600 last:border-0 items-center">
            <div className="col-span-5 min-w-0 text-sm text-ink-50 truncate">{d.caption.split("\n")[0]}</div>
            <div className="col-span-1"><PlatformBadge platform={d.platform} /></div>
            <div className="col-span-2 text-right font-mono text-xs text-ink-100 nums">{formatNumber(d.metrics?.impressions ?? 0)}</div>
            <div className="col-span-1 text-right font-mono text-xs text-ink-200 nums">{d.metrics?.likes ?? 0}</div>
            <div className="col-span-1 text-right font-mono text-xs text-ink-200 nums">{d.metrics?.comments ?? 0}</div>
            <div className="col-span-1 text-right font-mono text-xs text-ink-200 nums">{d.metrics?.shares ?? 0}</div>
            <div className="col-span-1 text-right font-mono text-2xs text-ink-300">{d.published_at ? formatRelative(d.published_at) : "—"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="col-span-6 md:col-span-4 lg:col-span-2 bg-ink-900 px-4 py-3.5">
      <div className="font-mono text-2xs uppercase tracking-wider text-ink-300">{label}</div>
      <div className="mt-1 font-display text-xl font-medium text-ink-50 nums">{value}</div>
      <div className="mt-0.5 text-xs text-ink-300">{sub}</div>
    </div>
  );
}
