import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Browser-side client. Reads from public env vars. Both must be defined for
// the real backend to activate; otherwise realtime features stay disabled.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(url && anon);

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!isSupabaseConfigured) return null;
  if (!client) {
    client = createClient(url!, anon!, {
      auth: { persistSession: false, autoRefreshToken: false },
      realtime: { params: { eventsPerSecond: 10 } },
    });
  }
  return client;
}

// Table names — single source of truth so the rest of the app does not
// hard-code strings.
export const TABLES = {
  documents: "documents",
  knowledgeChunks: "knowledge_chunks",
  postRuns: "post_runs",
  postDrafts: "post_drafts",
  agentLogs: "agent_logs",
  publishResults: "publish_results",
  brand: "brand",
} as const;

// Supabase Realtime channel name pattern
export const realtimeChannels = {
  runs: (runId: string) => `run:${runId}`,
  drafts: () => `drafts:public`,
  logs: (runId: string) => `logs:${runId}`,
};
