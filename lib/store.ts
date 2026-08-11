"use client";

// Centralized data store. Subscribes to Supabase Realtime when configured;
// otherwise serves mock data and listens to the local simulator. All callers
// go through the same hooks so the UI does not know which backend is active.

import { useEffect, useState, useCallback, useRef } from "react";
import { getSupabase } from "./supabase";
import {
  mockAgentLogs,
  mockBrand,
  mockDocuments,
  mockDrafts,
  mockInsights,
  mockRuns,
  mockTimeline,
} from "./mock-data";
import type {
  AgentLog,
  Brand,
  Document,
  PostDraft,
  PostRun,
  ResearchInsight,
  TimelineEvent,
  AgentKind,
  RunStatus,
} from "./types";

type Listener = () => void;

class Store {
  brand: Brand = mockBrand;
  runs: PostRun[] = mockRuns;
  drafts: PostDraft[] = mockDrafts;
  documents: Document[] = mockDocuments;
  insights: ResearchInsight[] = mockInsights;
  agentLogs: AgentLog[] = mockAgentLogs;
  timeline: TimelineEvent[] = mockTimeline;

  listeners = new Set<Listener>();

  subscribe(fn: Listener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit() {
    this.listeners.forEach((fn) => fn());
  }

  patch(partial: Partial<Pick<Store, "runs" | "drafts" | "timeline" | "agentLogs" | "documents" | "insights">>) {
    Object.assign(this, partial);
    this.emit();
  }

  appendTimeline(event: TimelineEvent) {
    this.timeline = [...this.timeline, event];
    this.emit();
  }

  updateDraft(id: string, patch: Partial<PostDraft>) {
    this.drafts = this.drafts.map((d) => (d.id === id ? { ...d, ...patch } : d));
    this.emit();
  }

  updateRun(id: string, patch: Partial<PostRun>) {
    this.runs = this.runs.map((r) => (r.id === id ? { ...r, ...patch } : r));
    this.emit();
  }

  addDocument(doc: Document) {
    this.documents = [doc, ...this.documents];
    this.emit();
  }

  updateDocument(id: string, patch: Partial<Document>) {
    this.documents = this.documents.map((d) => (d.id === id ? { ...d, ...patch } : d));
    this.emit();
  }
}

let store: Store | null = null;
export function getStore(): Store {
  if (!store) store = new Store();
  return store;
}

// ---------- hooks ----------

function useStoreState<T>(selector: (s: Store) => T): T {
  const [, force] = useState(0);
  const storeRef = useRef<Store>();
  if (!storeRef.current) storeRef.current = getStore();

  useEffect(() => {
    const unsubscribe = storeRef.current!.subscribe(() => force((n) => n + 1));
    return () => {
      unsubscribe();
    };
  }, []);

  return selector(storeRef.current!);
}

export function useBrand() {
  return useStoreState((s) => s.brand);
}
export function useRuns() {
  return useStoreState((s) => s.runs);
}
export function useDrafts() {
  return useStoreState((s) => s.drafts);
}
export function useDocuments() {
  return useStoreState((s) => s.documents);
}
export function useInsights() {
  return useStoreState((s) => s.insights);
}
export function useAgentLogs() {
  return useStoreState((s) => s.agentLogs);
}
export function useTimeline() {
  return useStoreState((s) => s.timeline);
}

// ---------- Supabase wiring ----------

let realtimeStarted = false;
export async function bootstrapRealtime() {
  if (realtimeStarted) return;
  realtimeStarted = true;
  const supa = getSupabase();
  if (!supa) return;

  const s = getStore();

  // Switch from mock data to real data state when configured
  s.runs = [];
  s.drafts = [];
  s.documents = [];
  s.insights = [];
  s.agentLogs = [];
  s.timeline = [];
  s.listeners.forEach((fn) => fn());

  // Fetch initial state from Supabase
  try {
    const [runsRes, draftsRes, docsRes, insightsRes, logsRes] = await Promise.all([
      supa.from("post_runs").select("*").order("created_at", { ascending: false }),
      supa.from("post_drafts").select("*").order("created_at", { ascending: false }),
      supa.from("documents").select("*").order("uploaded_at", { ascending: false }),
      supa.from("research_insights").select("*").order("captured_at", { ascending: false }),
      supa.from("agent_logs").select("*").order("started_at", { ascending: false }),
    ]);

    if (runsRes.data) s.runs = runsRes.data as PostRun[];
    if (draftsRes.data) s.drafts = draftsRes.data as PostDraft[];
    if (docsRes.data) s.documents = docsRes.data as Document[];
    if (insightsRes.data) s.insights = insightsRes.data as ResearchInsight[];
    if (logsRes.data) {
      s.agentLogs = logsRes.data as AgentLog[];
      s.timeline = logsRes.data.map((l: any) => ({
        id: l.id,
        run_id: l.run_id,
        agent: l.agent,
        label: l.agent,
        status: l.status === "complete" ? "complete" : l.status === "running" ? "running" : "pending",
        started_at: l.started_at,
        finished_at: l.finished_at ?? undefined,
        model: l.model,
        latency_ms: l.latency_ms,
        output_snippet: l.output_summary,
      }));
    }
    s.listeners.forEach((fn) => fn());
  } catch (err) {
    console.warn("Failed to fetch initial Supabase data:", err);
  }

  supa
    .channel("global")
    .on("postgres_changes", { event: "*", schema: "public", table: "post_drafts" }, (p) => {
      if (p.eventType === "INSERT") s.drafts = [p.new as PostDraft, ...s.drafts];
      if (p.eventType === "UPDATE") s.updateDraft((p.new as PostDraft).id, p.new as Partial<PostDraft>);
      if (p.eventType === "DELETE")
        s.drafts = s.drafts.filter((d) => d.id !== (p.old as { id: string }).id);
      s.listeners.forEach((fn) => fn());
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "post_runs" }, (p) => {
      if (p.eventType === "INSERT") s.runs = [p.new as PostRun, ...s.runs];
      if (p.eventType === "UPDATE") s.updateRun((p.new as PostRun).id, p.new as Partial<PostRun>);
      s.listeners.forEach((fn) => fn());
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "agent_logs" }, (p) => {
      const log = p.new as AgentLog;
      if (p.eventType === "INSERT" || p.eventType === "UPDATE") {
        s.agentLogs = [log, ...s.agentLogs.filter((l) => l.id !== log.id)];
        const ev: TimelineEvent = {
          id: log.id,
          run_id: log.run_id,
          agent: log.agent,
          label: log.agent,
          status: log.status === "complete" ? "complete" : log.status === "running" ? "running" : "pending",
          started_at: log.started_at,
          finished_at: log.finished_at ?? undefined,
          model: log.model,
          latency_ms: log.latency_ms,
          output_snippet: log.output_summary,
        };
        s.timeline = [ev, ...s.timeline.filter((t) => t.id !== ev.id)];
      }
      s.listeners.forEach((fn) => fn());
    })
    .subscribe();
}

// ---------- Simulated live pipeline ----------

// Drives the on-screen "live" timeline when no real backend is configured.
// Walks a new run through the pipeline, emitting TimelineEvent rows as each
// stage completes — the UI appears to be doing real work.

const SIM_LATENCIES: Record<string, number> = {
  research: 4200,
  knowledge: 1100,
  strategist: 1800,
  copywriter: 4500,
  visual: 2200,
  image_gen: 4800,
  approval: 0,
};

export function startSimulatedRun() {
  const s = getStore();
  const runId = `run_sim_${Date.now()}`;
  const startedAt = new Date().toISOString();

  const newRun: PostRun = {
    id: runId,
    started_at: startedAt,
    finished_at: null,
    status: "researching",
    trigger: "manual",
    draft_ids: [],
    current_agent: "research",
  };
  s.runs = [newRun, ...s.runs];

  const order: Array<{ agent: AgentKind | "image_gen"; label: string; model: string }> = [
    { agent: "research", label: "Research", model: "grok-4-fast" },
    { agent: "knowledge", label: "Knowledge", model: "grok-4 + RAG" },
    { agent: "strategist", label: "Strategist", model: "grok-4" },
    { agent: "copywriter", label: "Copywriter", model: "grok-4" },
    { agent: "visual", label: "Visual", model: "grok-4-vision" },
    { agent: "image_gen", label: "Image Generation", model: "flux-pro-1.1" },
  ];

  let elapsed = 0;
  order.forEach((stage, idx) => {
    const stageStart = elapsed;
    const latency = SIM_LATENCIES[stage.agent] ?? 2000;
    elapsed += latency;

    // mark running
    setTimeout(() => {
      const ev: TimelineEvent = {
        id: `tl_${runId}_${idx}`,
        run_id: runId,
        agent: stage.agent as AgentKind,
        label: stage.label,
        status: "running",
        started_at: new Date().toISOString(),
        model: stage.model,
      };
      s.appendTimeline(ev);
    }, stageStart);

    // mark complete
    setTimeout(() => {
      const completeEv: TimelineEvent = {
        id: `tl_${runId}_${idx}_done`,
        run_id: runId,
        agent: stage.agent as AgentKind,
        label: stage.label,
        status: "complete",
        started_at: new Date(Date.now() - latency).toISOString(),
        finished_at: new Date().toISOString(),
        model: stage.model,
        latency_ms: latency,
        output_snippet: stageOutputSnippet(stage.label),
      };
      s.appendTimeline(completeEv);
    }, stageStart + latency);
  });

  // After last stage, sit at awaiting_approval and create drafts
  setTimeout(() => {
    const awaiting: TimelineEvent = {
      id: `tl_${runId}_awaiting`,
      run_id: runId,
      agent: "knowledge",
      label: "Awaiting Approval",
      status: "running",
      started_at: new Date().toISOString(),
      model: "—",
      output_snippet: "Human checkpoint",
    };
    s.appendTimeline(awaiting);

    const statusMap: Record<string, RunStatus> = {
      research: "researching",
      knowledge: "strategizing",
      strategist: "strategizing",
      copywriter: "writing",
      visual: "designing",
      image_gen: "generating_image",
    };

    const newDrafts: PostDraft[] = [
      {
        id: `draft_sim_${runId}_ig`,
        run_id: runId,
        platform: "instagram",
        version: 1,
        caption: mockDrafts[0].caption,
        hashtags: mockDrafts[0].hashtags,
        image_url: mockDrafts[0].image_url,
        image_prompt: mockDrafts[0].image_prompt,
        strategy: mockDrafts[0].strategy,
        reasoning: mockDrafts[0].reasoning,
        status: "pending_approval",
        scheduled_for: new Date(Date.now() + 2 * 60 * 60_000).toISOString(),
        published_at: null,
        created_at: new Date().toISOString(),
      },
      {
        id: `draft_sim_${runId}_li`,
        run_id: runId,
        platform: "linkedin",
        version: 1,
        caption: mockDrafts[1].caption,
        hashtags: [],
        image_url: mockDrafts[1].image_url,
        image_prompt: mockDrafts[1].image_prompt,
        strategy: mockDrafts[1].strategy,
        reasoning: mockDrafts[1].reasoning,
        status: "pending_approval",
        scheduled_for: new Date(Date.now() + 2 * 60 * 60_000).toISOString(),
        published_at: null,
        created_at: new Date().toISOString(),
      },
    ];
    s.drafts = [...newDrafts, ...s.drafts];
    s.runs = s.runs.map((r) =>
      r.id === runId
        ? { ...r, status: "awaiting_approval", draft_ids: newDrafts.map((d) => d.id), current_agent: null }
        : r,
    );
    s.listeners.forEach((fn) => fn());
  }, elapsed);

  return runId;
}

function stageOutputSnippet(label: string): string {
  switch (label) {
    case "Research":
      return "12 trends, 4 competitor signals indexed";
    case "Knowledge":
      return "24 chunks retrieved · confidence 0.81";
    case "Strategist":
      return "Hook: 'Your board is a trust metric'";
    case "Copywriter":
      return "Drafts ready, voice-checked";
    case "Visual":
      return "Selected hero concept, prompt finalized";
    case "Image Generation":
      return "2 hero images rendered at 2048×2048";
    default:
      return "Stage complete";
  }
}

// ---------- Actions ----------

export function useApproveAction() {
  const store = getStore();
  const cb = useCallback(
    async (draftId: string, action: "approve" | "reject" | "regenerate", feedback?: string) => {
      if (action === "approve") {
        store.updateDraft(draftId, { status: "approved" });
        // Simulate publish
        setTimeout(() => {
          store.updateDraft(draftId, { status: "published", published_at: new Date().toISOString() });
        }, 1400);
      } else if (action === "reject") {
        store.updateDraft(draftId, { status: "rejected" });
      } else {
        store.updateDraft(draftId, { status: "draft" });
      }
    },
    [store],
  );
  return cb;
}
