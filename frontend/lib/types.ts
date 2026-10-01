// Kelvin6k domain types — mirror the Supabase schema.
// Keep secret-bearing fields (model keys, raw prompt payloads) server-side.

export type Platform = "instagram" | "linkedin";

export type RunStatus =
  | "queued"
  | "researching"
  | "strategizing"
  | "writing"
  | "designing"
  | "generating_image"
  | "awaiting_idea_selection"
  | "generating_drafts"
  | "awaiting_approval"
  | "publishing"
  | "published"
  | "rejected"
  | "failed";

export type DraftStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "published";

export type DocumentStatus = "uploading" | "processing" | "indexing" | "indexed" | "failed";

export type AgentKind =
  | "strategist"
  | "research"
  | "copywriter"
  | "visual"
  | "knowledge"
  | "publisher";

export interface Brand {
  id: string;
  name?: string;
  company_name?: string;
  website?: string | null;
  industry: string;
  voice?: string;
  audience?: string;
  brand_voice?: string | null;
  target_audience?: string;
  products_services?: string | null;
  competitors: string[];
  model?: string;
  ig_handle?: string | null;
  li_handle?: string | null;
  instagram_handle?: string | null;
  linkedin_handle?: string | null;
  goals?: string | null;
  content_themes?: string[];
  reference_images?: string[];
  approval_channel?: "none" | "telegram";
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  telegram_webhook_secret?: string | null;
  updated_at?: string;
}

export interface Document {
  id: string;
  file_name: string;
  mime_type: string;
  status: DocumentStatus;
  storage_path: string;
  created_at: string;
  chunks: number;
  pages: number;
  error?: string;
}

export interface KnowledgeChunk {
  id: string;
  document_id: string;
  content: string;
  embedding_dim: number;
  source_label: string;
}

export interface ResearchInsight {
  id: string;
  title: string;
  summary: string;
  source: string;
  source_kind: "industry" | "competitor" | "trend" | "recommendation";
  url?: string;
  tags: string[];
  captured_at: string;
  related_count?: number;
}

export interface Idea {
  index: number;
  angle: string;
  headline: string;
  summary: string;
  format?: string;
  format_label?: string;
  image_hint?: string;
}

export interface PostRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  trigger: "scheduled" | "manual" | "regenerate";
  draft_ids: string[];
  current_agent: AgentKind | null;
  notes?: string;
  ideas?: Idea[];
  selected_idea_indices?: number[];
  idea_status?: "not_proposed" | "proposed" | "selected" | "generating" | "done" | "dismissed";
}

export interface PostDraft {
  id: string;
  run_id: string;
  platform: Platform;
  version: number;
  caption: string;
  hashtags: string[];
  image_url: string | null;
  image_prompt?: string;
  strategy?: string;
  reasoning?: string;
  status: DraftStatus;
  scheduled_for: string | null;
  published_at: string | null;
  idea_index?: number | null;
  format?: string | null;
  format_label?: string | null;
  image_hint?: string | null;
  metrics?: {
    qa_status?: string;
    image_provider_used?: string;
    degraded_steps?: string[];
    likes?: number;
    comments?: number;
    shares?: number;
    impressions?: number;
  };
  created_at: string;
}

export interface AgentLog {
  id: string;
  run_id: string;
  agent: AgentKind;
  model: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "complete" | "error";
  input_summary?: string;
  output_summary?: string;
  latency_ms?: number;
  tokens_in?: number;
  tokens_out?: number;
}

export interface PublishResult {
  id: string;
  draft_id: string;
  platform: Platform;
  published_at: string;
  external_url?: string;
  status: "success" | "failed";
  error?: string;
}

export interface ApprovalAction {
  draft_id: string;
  action: "approve" | "reject" | "regenerate";
  feedback?: string;
  decided_by: string;
  decided_at: string;
}

// Realtime timeline event
export interface TimelineEvent {
  id: string;
  run_id: string;
  agent: AgentKind;
  label: string;
  status: "complete" | "running" | "pending";
  started_at: string;
  finished_at?: string;
  model?: string;
  latency_ms?: number;
  output_snippet?: string;
}

export const AGENT_META: Record<
  AgentKind,
  { name: string; role: string; color: string; model: string; index: number }
> = {
  research: {
    name: "Research",
    role: "Industry & competitor discovery",
    color: "#6B8AFF",
    model: "llama-3.3-70b-versatile",
    index: 0,
  },
  strategist: {
    name: "Strategist",
    role: "Plans messages & angles",
    color: "#F5B947",
    model: "llama-3.3-70b-versatile",
    index: 1,
  },
  copywriter: {
    name: "Copywriter",
    role: "Writes platform-native captions",
    color: "#F5B947",
    model: "llama-3.3-70b-versatile",
    index: 2,
  },
  visual: {
    name: "Visual",
    role: "Composes image concepts",
    color: "#94AEFF",
    model: "llama-3.3-70b-versatile",
    index: 3,
  },
  knowledge: {
    name: "Knowledge",
    role: "Retrieves brand context",
    color: "#4ADE80",
    model: "grok-4 + RAG",
    index: 4,
  },
  publisher: {
    name: "Publisher",
    role: "Posts to Instagram & LinkedIn",
    color: "#94AEFF",
    model: "Meta Graph API",
    index: 5,
  },
};

export const PIPELINE_STAGES: Array<{
  key: AgentKind | "image_gen" | "approval";
  label: string;
  hint: string;
}> = [
  { key: "research", label: "Research", hint: "Trends, competitors, signals" },
  { key: "knowledge", label: "Knowledge", hint: "Brand context retrieval" },
  { key: "strategist", label: "Strategist", hint: "Angles & message hierarchy" },
  { key: "copywriter", label: "Copywriter", hint: "Platform-native voice" },
  { key: "visual", label: "Visual", hint: "Image concept & prompt" },
  { key: "image_gen", label: "Image Generation", hint: "Render visual" },
  { key: "approval", label: "Awaiting Approval", hint: "Human checkpoint" },
  { key: "publisher", label: "Publisher", hint: "Push to platforms" },
];
