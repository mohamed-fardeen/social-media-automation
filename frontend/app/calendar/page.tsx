"use client";

import { useState, useMemo } from "react";
import { useDrafts } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlatformBadge } from "@/components/ui/PlatformIcon";
import { StatusDot } from "@/components/ui/StatusDot";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, List, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  format,
  addMonths,
  subMonths,
  isSameMonth,
  isSameDay,
  parseISO,
} from "date-fns";

type View = "month" | "week" | "list";

export default function CalendarPage() {
  const drafts = useDrafts();
  const [view, setView] = useState<View>("month");
  const [cursor, setCursor] = useState<Date>(new Date(2026, 7, 11)); // Aug 11, 2026

  const scheduled = useMemo(
    () => drafts.filter((d) => d.scheduled_for || d.published_at),
    [drafts],
  );

  const monthStart = startOfMonth(cursor);
  const monthEnd = endOfMonth(cursor);
  const gridStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: gridStart, end: gridEnd });

  const itemsByDay = useMemo(() => {
    const map = new Map<string, typeof drafts>();
    for (const d of scheduled) {
      const date = d.published_at ?? d.scheduled_for;
      if (!date) continue;
      const key = format(parseISO(date), "yyyy-MM-dd");
      const arr = map.get(key) ?? [];
      arr.push(d);
      map.set(key, arr);
    }
    return map;
  }, [scheduled]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Calendar"
        title="The publishing schedule."
        description="Drafts in motion, pending approval, and live on the platforms. Move a post to reschedule."
        actions={
          <div className="flex items-center gap-px border border-ink-600 rounded-md p-0.5 bg-ink-900">
            {[
              { v: "month" as View, icon: LayoutGrid, label: "Month" },
              { v: "week" as View, icon: CalendarIcon, label: "Week" },
              { v: "list" as View, icon: List, label: "List" },
            ].map((opt) => (
              <button
                key={opt.v}
                onClick={() => setView(opt.v)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-[12px] font-medium transition-colors",
                  view === opt.v ? "bg-ink-750 text-ink-50" : "text-ink-200 hover:text-ink-50",
                )}
              >
                <opt.icon className="h-3.5 w-3.5" />
                {opt.label}
              </button>
            ))}
          </div>
        }
      />

      {view !== "list" && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setCursor((c) => subMonths(c, 1))}
              className="grid h-8 w-8 place-items-center rounded-md border border-ink-600 bg-ink-900 text-ink-200 hover:text-ink-50 hover:border-ink-500"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <h2 className="font-display text-2xl font-medium text-ink-50">
              {format(cursor, "MMMM yyyy")}
            </h2>
            <button
              onClick={() => setCursor((c) => addMonths(c, 1))}
              className="grid h-8 w-8 place-items-center rounded-md border border-ink-600 bg-ink-900 text-ink-200 hover:text-ink-50 hover:border-ink-500"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Chip label={`${scheduled.filter((d) => d.status === "pending_approval").length} pending`} tone="sodium" />
            <Chip label={`${scheduled.filter((d) => d.status === "published").length} published`} tone="success" />
          </div>
        </div>
      )}

      {view === "month" && (
        <div className="rounded-xl border border-ink-600 overflow-hidden">
          <div className="grid grid-cols-7 bg-ink-850 border-b border-ink-600">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <div key={d} className="px-3 py-2 font-mono text-2xs uppercase tracking-wider text-ink-300">
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 grid-rows-6">
            {days.map((day) => {
              const inMonth = isSameMonth(day, cursor);
              const isToday = isSameDay(day, new Date(2026, 7, 11));
              const items = itemsByDay.get(format(day, "yyyy-MM-dd")) ?? [];
              return (
                <div
                  key={day.toISOString()}
                  className={cn(
                    "min-h-[110px] border-b border-r border-ink-600 p-2 transition-colors",
                    inMonth ? "bg-ink-900" : "bg-ink-950/40",
                    "hover:bg-ink-850",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        "inline-flex items-center justify-center h-6 w-6 rounded-full font-mono text-xs",
                        isToday
                          ? "bg-sodium-500 text-ink-950"
                          : inMonth
                            ? "text-ink-100"
                            : "text-ink-400",
                      )}
                    >
                      {format(day, "d")}
                    </span>
                  </div>
                  <div className="mt-1 space-y-1">
                    {items.slice(0, 2).map((d) => (
                      <Link
                        key={d.id}
                        href={`/studio/${d.id}`}
                        className="block text-[11px] truncate text-ink-100 hover:text-sodium-500"
                        title={d.caption.slice(0, 60)}
                      >
                        <span className="font-mono mr-1">
                          {d.platform === "instagram" ? "IG" : "LI"}
                        </span>
                        {d.caption.split("\n")[0].slice(0, 40)}
                      </Link>
                    ))}
                    {items.length > 2 && (
                      <div className="font-mono text-2xs text-ink-300">+{items.length - 2} more</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {view === "week" && (
        <div className="rounded-xl border border-ink-600 overflow-hidden">
          <div className="grid grid-cols-7">
            {days.slice(0, 7).map((day) => {
              const items = itemsByDay.get(format(day, "yyyy-MM-dd")) ?? [];
              return (
                <div key={day.toISOString()} className="border-r border-ink-600 last:border-r-0 bg-ink-900 min-h-[420px]">
                  <div className="border-b border-ink-600 px-3 py-2 flex items-center justify-between">
                    <span className="font-mono text-2xs uppercase tracking-wider text-ink-300">{format(day, "EEE")}</span>
                    <span className="font-display text-lg text-ink-50">{format(day, "d")}</span>
                  </div>
                  <div className="p-2 space-y-2">
                    {items.map((d) => (
                      <Link
                        key={d.id}
                        href={`/studio/${d.id}`}
                        className="block rounded-md border border-ink-600 bg-ink-850 p-2 hover:border-ink-500"
                      >
                        <div className="flex items-center justify-between">
                          <PlatformBadge platform={d.platform} />
                          <StatusDot
                            status={d.status === "published" ? "published" : d.status === "pending_approval" ? "pending" : "draft"}
                          />
                        </div>
                        <p className="mt-1.5 text-[11px] text-ink-200 line-clamp-2">{d.caption.split("\n")[0]}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {view === "list" && (
        <div className="rounded-xl border border-ink-600 overflow-hidden">
          <div className="grid grid-cols-12 bg-ink-850 px-4 py-2.5 font-mono text-2xs uppercase tracking-wider text-ink-300 border-b border-ink-600">
            <div className="col-span-2">When</div>
            <div className="col-span-1">Platform</div>
            <div className="col-span-7">Post</div>
            <div className="col-span-2 text-right">Status</div>
          </div>
          {scheduled
            .slice()
            .sort((a, b) => {
              const aT = a.published_at ?? a.scheduled_for ?? a.created_at;
              const bT = b.published_at ?? b.scheduled_for ?? b.created_at;
              return new Date(aT).getTime() - new Date(bT).getTime();
            })
            .map((d) => (
              <Link
                key={d.id}
                href={`/studio/${d.id}`}
                className="grid grid-cols-12 gap-4 px-4 py-3.5 border-b border-ink-600 last:border-0 items-center hover:bg-ink-850/50"
              >
                <div className="col-span-2">
                  <div className="font-mono text-xs text-ink-100 nums">
                    {format(parseISO(d.published_at ?? d.scheduled_for ?? d.created_at), "MMM d")}
                  </div>
                  <div className="font-mono text-2xs text-ink-300">{format(parseISO(d.published_at ?? d.scheduled_for ?? d.created_at), "HH:mm")}</div>
                </div>
                <div className="col-span-1">
                  <PlatformBadge platform={d.platform} />
                </div>
                <div className="col-span-7 min-w-0">
                  <div className="text-sm text-ink-50 truncate">{d.caption.split("\n")[0]}</div>
                </div>
                <div className="col-span-2 text-right">
                  <StatusDot
                    status={d.status === "published" ? "published" : d.status === "pending_approval" ? "pending" : d.status === "approved" ? "approved" : d.status === "rejected" ? "rejected" : "draft"}
                    withLabel
                  />
                </div>
              </Link>
            ))}
        </div>
      )}
    </div>
  );
}
