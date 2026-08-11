"use client";

import { Search } from "lucide-react";
import { LiveClock } from "@/components/ui/LiveClock";
import { Button } from "@/components/ui/Button";
import { Sparkles } from "lucide-react";
import { useRuns } from "@/lib/store";

export function Topbar() {
  const runs = useRuns();
  const live = runs.find((r) => r.status === "awaiting_approval" || r.status === "researching" || r.status === "writing" || r.status === "designing" || r.status === "publishing");

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-ink-600 bg-ink-950/80 px-6 py-3 backdrop-blur-xl">
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-mono text-2xs uppercase tracking-wider text-ink-300">/</span>
        <span className="font-mono text-2xs uppercase tracking-wider text-ink-200 truncate">
          Kelvin6k / Atlas
        </span>
      </div>

      <div className="ml-6 flex-1 max-w-md">
        <label className="relative flex items-center gap-2 rounded-md border border-ink-600 bg-ink-850 px-2.5 h-8 text-[13px] text-ink-300 focus-within:border-ink-500">
          <Search className="h-3.5 w-3.5 text-ink-300" />
          <input
            placeholder="Search posts, agents, documents…"
            className="bg-transparent outline-none flex-1 placeholder:text-ink-300"
          />
          <span className="font-mono text-2xs text-ink-400 border border-ink-600 rounded px-1.5 py-0.5">⌘K</span>
        </label>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-md border border-ink-600 bg-ink-850 px-2.5 h-8">
          {live ? (
            <>
              <span className="relative inline-flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-sodium-500 animate-pulse-ring" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-sodium-500" />
              </span>
              <span className="font-mono text-2xs uppercase tracking-wider text-ink-100">
                Run in progress · {live.current_agent ?? "live"}
              </span>
            </>
          ) : (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-live-ok" />
              <span className="font-mono text-2xs uppercase tracking-wider text-ink-200">All systems nominal</span>
            </>
          )}
        </div>

        <LiveClock />

        <a href="/" className="contents">
          <Button variant="primary" size="md" iconLeft={<Sparkles className="h-3.5 w-3.5" />}>
            Generate Now
          </Button>
        </a>
      </div>
    </header>
  );
}
