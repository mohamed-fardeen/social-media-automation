"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSupabase } from "./supabase";
import type {
  AgentKind,
  AgentLog,
  Brand,
  Document,
  PostDraft,
  PostRun,
  ResearchInsight,
  TimelineEvent,
} from "./types";

type Listener = () => void;

class Store {
  brand: Brand = {
    id: "default",
    company_name: "",
    name: "",
    industry: "",
    target_audience: "",
    audience: "",
    voice: "",
    competitors: [],
    model: "llama-3.3-70b-versatile",
    ig_handle: "",
    li_handle: "",
    content_themes: [],
  };
  runs: PostRun[] = [];
  drafts: PostDraft[] = [];
  documents: Document[] = [];
  insights: ResearchInsight[] = [];
  agentLogs: AgentLog[] = [];
  timeline: TimelineEvent[] = [];

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
    this.timeline = [event, ...this.timeline.filter((item) => item.id !== event.id)];
    this.emit();
  }

  updateBrand(patch: Partial<Brand>) {
    this.brand = { ...this.brand, ...patch };
    this.emit();
  }

  updateDraft(id: string, patch: Partial<PostDraft>) {
    this.drafts = this.drafts.map((draft) => (draft.id === id ? { ...draft, ...patch } : draft));
    this.emit();
  }

  updateRun(id: string, patch: Partial<PostRun>) {
    this.runs = this.runs.map((run) => (run.id === id ? { ...run, ...patch } : run));
    this.emit();
  }

  addDocument(doc: Document) {
    this.documents = [doc, ...this.documents];
    this.emit();
  }

  updateDocument(id: string, patch: Partial<Document>) {
    this.documents = this.documents.map((doc) => (doc.id === id ? { ...doc, ...patch } : doc));
    this.emit();
  }

  removeDocument(id: string) {
    this.documents = this.documents.filter((doc) => doc.id !== id);
    this.emit();
  }
}

let store: Store | null = null;

export function getStore(): Store {
  if (!store) store = new Store();
  return store;
}

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

/**
 * Refetch drafts from Supabase. A realtime INSERT is missed whenever the channel
 * drops or post_drafts is not in the supabase_realtime publication, so pages that
 * render drafts refetch instead of trusting the socket alone.
 */
export async function refreshDrafts() {
  const supa = getSupabase();
  if (!supa) return;
  const s = getStore();
  const { data, error } = await supa
    .from("post_drafts")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) {
    console.warn("Failed to refresh post_drafts:", error.message);
    return;
  }
  if (data) s.patch({ drafts: normalizeDrafts(data) });
}

/** Drafts plus an on-mount / on-focus / periodic refetch. */
export function useDraftsLive() {
  const drafts = useDrafts();
  useEffect(() => {
    refreshDrafts();
    const onFocus = () => refreshDrafts();
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(refreshDrafts, 15000);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, []);
  return drafts;
}

/** Insights refetch — same pattern as refreshDrafts so Telegram-driven runs
 * show up in the web UI without waiting for the realtime channel. */
export async function refreshInsights() {
  const supa = getSupabase();
  if (!supa) return;
  const s = getStore();
  const { data, error } = await supa
    .from("research_insights")
    .select("*")
    .order("captured_at", { ascending: false });
  if (error) {
    console.warn("Failed to refresh research_insights:", error.message);
    return;
  }
  if (data) s.patch({ insights: data as ResearchInsight[] });
}

export function useInsightsLive() {
  const insights = useInsights();
  useEffect(() => {
    refreshInsights();
    const onFocus = () => refreshInsights();
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(refreshInsights, 20000);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, []);
  return insights;
}

/** Runs refetch — the Telegram selection round updates post_runs.ideas and
 * selected_idea_indices; this ensures the UI reflects those without relying
 * on realtime. */
export async function refreshRuns() {
  const supa = getSupabase();
  if (!supa) return;
  const s = getStore();
  const { data, error } = await supa
    .from("post_runs")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) {
    console.warn("Failed to refresh post_runs:", error.message);
    return;
  }
  if (data) s.patch({ runs: data as PostRun[] });
}

export function useRunsLive() {
  const runs = useRuns();
  useEffect(() => {
    refreshRuns();
    const onFocus = () => refreshRuns();
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(refreshRuns, 10000);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, []);
  return runs;
}

/** Like useDraftsLive, but also reports whether the first fetch has settled. */
export function useDraftsLoaded(): { drafts: PostDraft[]; loading: boolean } {
  const drafts = useDraftsLive();
  const [loading, setLoading] = useState(drafts.length === 0);
  useEffect(() => {
    let cancelled = false;
    refreshDrafts().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return { drafts, loading };
}

let realtimeStarted = false;

export async function bootstrapRealtime() {
  if (realtimeStarted) return;
  realtimeStarted = true;

  const supa = getSupabase();
  if (!supa) return;

  const s = getStore();

  try {
    const { data } = await supa.from("brand_profiles").select("*").eq("id", "default").single();
    if (data) s.updateBrand(data as Partial<Brand>);
  } catch (err) {
    console.warn("Failed to fetch brand profile:", err);
  }

  try {
    const { data } = await supa.from("post_runs").select("*").order("created_at", { ascending: false });
    if (data) s.runs = data as PostRun[];
  } catch (err) {
    console.warn("Failed to fetch post_runs:", err);
  }

  try {
    const { data } = await supa.from("post_drafts").select("*").order("created_at", { ascending: false });
    if (data) s.drafts = normalizeDrafts(data);
  } catch (err) {
    console.warn("Failed to fetch post_drafts:", err);
  }

  try {
    const { data } = await supa.from("documents").select("*").order("created_at", { ascending: false });
    if (data) s.documents = data.map(normalizeDocument);
  } catch (err) {
    console.warn("Failed to fetch documents:", err);
  }

  try {
    const { data } = await supa.from("research_insights").select("*").order("captured_at", { ascending: false });
    if (data) s.insights = data as ResearchInsight[];
  } catch (err) {
    console.warn("Failed to fetch research_insights:", err);
  }

  try {
    const { data } = await supa.from("agent_logs").select("*").order("created_at", { ascending: false });
    if (data) {
      s.agentLogs = data.map(normalizeAgentLog);
      s.timeline = s.agentLogs.map(agentLogToTimeline);
    }
  } catch (err) {
    console.warn("Failed to fetch agent_logs:", err);
  }

  s.listeners.forEach((fn) => fn());

  supa
    .channel("global")
    .on("postgres_changes", { event: "*", schema: "public", table: "brand_profiles" }, (payload) => {
      if (payload.eventType === "INSERT" || payload.eventType === "UPDATE") {
        s.updateBrand(payload.new as Partial<Brand>);
      }
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "post_drafts" }, (payload) => {
      const draft = normalizeDraft(payload.new as Record<string, any>);
      if (payload.eventType === "INSERT") s.drafts = [draft, ...s.drafts.filter((item) => item.id !== draft.id)];
      if (payload.eventType === "UPDATE") s.updateDraft(draft.id, draft);
      if (payload.eventType === "DELETE") s.drafts = s.drafts.filter((item) => item.id !== (payload.old as { id: string }).id);
      s.listeners.forEach((fn) => fn());
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "post_runs" }, (payload) => {
      const run = payload.new as PostRun;
      if (payload.eventType === "INSERT") s.runs = [run, ...s.runs.filter((item) => item.id !== run.id)];
      if (payload.eventType === "UPDATE") s.updateRun(run.id, run);
      s.listeners.forEach((fn) => fn());
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "research_insights" }, (payload) => {
      const insight = payload.new as ResearchInsight;
      if (payload.eventType === "INSERT") s.insights = [insight, ...s.insights.filter((item) => item.id !== insight.id)];
      if (payload.eventType === "UPDATE") {
        s.insights = s.insights.map((item) => (item.id === insight.id ? insight : item));
      }
      if (payload.eventType === "DELETE") s.insights = s.insights.filter((item) => item.id !== (payload.old as { id: string }).id);
      s.listeners.forEach((fn) => fn());
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "agent_logs" }, (payload) => {
      if (payload.eventType === "INSERT" || payload.eventType === "UPDATE") {
        const log = normalizeAgentLog(payload.new as Record<string, any>);
        s.agentLogs = [log, ...s.agentLogs.filter((item) => item.id !== log.id)];
        s.appendTimeline(agentLogToTimeline(log));
      }
    })
    .subscribe((status) => {
      if (status === "CHANNEL_ERROR" || status === "TIMED_OUT" || status === "CLOSED") {
        console.warn(`[realtime] channel status: ${status} — falling back to refetch`);
      }
    });
}

export function useApproveAction() {
  const store = getStore();
  return useCallback(
    async (
      runId: string,
      draftId: string,
      action: "approve" | "reject" | "regenerate",
      feedback?: string,
    ) => {
      // Optimistic local update
      if (action === "approve") store.updateDraft(draftId, { status: "approved" });
      if (action === "reject") store.updateDraft(draftId, { status: "rejected" });
      if (action === "regenerate") store.updateDraft(draftId, { status: "draft" });

      // Persist to backend
      const { api } = await import("./api");
      await api.approvalAction(runId, {
        draft_id: draftId,
        action,
        feedback,
      });
    },
    [store],
  );
}

function normalizeDocument(row: Record<string, any>): Document {
  return {
    id: row.id,
    file_name: row.file_name,
    mime_type: row.mime_type,
    status: row.status,
    storage_path: row.storage_path,
    created_at: row.created_at,
    chunks: row.chunks ?? 0,
    pages: row.pages ?? 0,
    error: row.error,
  };
}

function normalizeDrafts(rows: any[]): PostDraft[] {
  return rows.map(normalizeDraft);
}

function normalizeDraft(row: Record<string, any>): PostDraft {
  return {
    ...row,
    hashtags: Array.isArray(row.hashtags)
      ? row.hashtags
      : typeof row.hashtags === "string" && row.hashtags
        ? row.hashtags.split(",").map((item: string) => item.trim()).filter(Boolean)
        : [],
  } as PostDraft;
}

function normalizeAgentLog(row: Record<string, any>): AgentLog {
  return {
    id: row.id,
    run_id: row.run_id,
    agent: (row.agent || row.agent_name || "research") as AgentKind,
    model: row.model || "llama-3.3-70b-versatile",
    started_at: row.started_at || row.created_at,
    finished_at: row.finished_at || null,
    status: row.status || "complete",
    input_summary: row.input_summary || row.input || "",
    output_summary: row.output_summary || row.output || "",
    latency_ms: row.latency_ms,
  };
}

function agentLogToTimeline(log: AgentLog): TimelineEvent {
  return {
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
}
