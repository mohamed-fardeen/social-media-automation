// Thin API client for the Python FastAPI backend.
// Reads backend endpoints from process.env with clean local fallbacks.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

const INGEST_URL = process.env.NEXT_PUBLIC_INGEST_URL || `${API_BASE}/ingest`;
const INGEST_UPLOAD_URL = `${API_BASE}/ingest/upload`;
const RUN_URL = process.env.NEXT_PUBLIC_RUN_URL || `${API_BASE}/runs`;

export type IngestPayload = {
  source: "document" | "url" | "note";
  filename?: string;
  storage_path?: string;
  url?: string;
  text?: string;
  brand_id?: string;
};

export type UploadResult = {
  document_id: string;
  name: string;
  size_bytes: number;
  status: string;
  storage_path: string;
};

export type DocumentResult = {
  id: string;
  file_name: string;
  mime_type: string;
  status: string;
  storage_path: string;
  created_at: string;
  chunks: number;
  pages: number;
  error?: string;
};

export type ProductOneLiner = {
  name: string;
  one_liner: string;
};

export type ProjectOneLiner = {
  name: string;
  one_liner: string;
};

export type HardConstraints = {
  never_invent: string[];
  product_naming: string[];
  unknown_handling: string;
};

export type BrandProfile = {
  id?: string;
  company_name: string;
  website?: string | null;
  industry: string;
  target_audience: string;
  brand_voice?: string | null;
  brand_principle?: string | null;
  post_length?: "short" | "medium" | "long";
  image_primary_provider?: "openai" | "gemini" | "gemini_web";
  image_openai_model?: string;
  image_openai_quality?: "low" | "medium" | "high";
  competitors?: string[];
  products?: ProductOneLiner[];
  projects?: ProjectOneLiner[];
  hard_constraints?: HardConstraints;
  reference_images?: string[];
  instagram_handle?: string | null;
  linkedin_handle?: string | null;
  approval_channel?: "none" | "telegram";
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  telegram_webhook_secret?: string | null;
  updated_at?: string;
};

export type EntitySuggestion = {
  id: string;
  type: "product" | "project";
  name: string;
  context: string;
  source_doc: string;
  status: "pending" | "approved" | "ignored";
  created_at: string;
};

export type ReferenceImage = {
  id: string;
  image_url: string;
  linked_to_type: string;
  linked_to_name: string;
  uploaded_at: string;
};

export type TelegramConnectPayload = {
  telegram_bot_token: string;
  telegram_chat_id: string;
  telegram_webhook_secret?: string | null;
  approval_channel?: "telegram";
};

export type ResearchRunResult = {
  insights: any[];
  evidence_count: number;
};

export type RunNowPayload = {
  brand_id?: string;
  platforms?: Array<"instagram" | "linkedin">;
  topic?: string;
  notes?: string;
  mode?: "full_pipeline" | "draft_only";
  image_mode?: "text_only" | "with_image" | "mix";
  source_mode?: "research" | "user_topic";
  user_topic?: string;
  country_scope?: "global" | "india";
  trigger?: string;
};

export type ApprovalAction = {
  draft_id: string;
  action: "approve" | "reject" | "regenerate" | "dismiss";
  feedback?: string;
  decided_by?: string;
};

export type RagCitation = {
  index: number;
  source: string;
  page?: number;
  similarity?: number;
};

export type RagChatResult = {
  answer: string;
  citations: RagCitation[];
};

async function post<T>(url: string, body: unknown): Promise<T | null> {
  if (!url) {
    console.info(`[api] POST skipped because no URL is configured`, body);
    await new Promise((r) => setTimeout(r, 250));
    return null;
  }
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      console.warn(`[api] ${url} failed: ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[api] ${url} error`, err);
    return null;
  }
}

async function get<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.warn(`[api] ${url} failed: ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[api] ${url} error`, err);
    return null;
  }
}

async function del<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) {
      console.warn(`[api] ${url} failed: ${res.status}`, await res.text());
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[api] ${url} error`, err);
    return null;
  }
}

export const api = {
  ingest: (payload: IngestPayload) =>
    post<{ ok: true; data?: any }>(INGEST_URL, payload),

  /**
   * Upload a file directly to the backend via multipart/form-data.
   * The backend handles Supabase storage, chunking, and embedding.
   * Returns the document_id so the caller can poll for status.
   */
  uploadDocument: async (file: File): Promise<UploadResult | null> => {
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const res = await fetch(INGEST_UPLOAD_URL, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        console.warn(`[api] upload failed: ${res.status}`, await res.text());
        return null;
      }
      const json = (await res.json()) as { ok: boolean; data: UploadResult };
      return json?.data ?? null;
    } catch (err) {
      console.warn("[api] upload error", err);
      return null;
    }
  },

  listDocuments: async (): Promise<DocumentResult[]> => {
    const res = await get<{ ok: true; data?: { documents: DocumentResult[] } }>(`${API_BASE}/documents`);
    return res?.data?.documents ?? [];
  },

  getDocument: async (documentId: string): Promise<DocumentResult | null> => {
    const res = await get<{ ok: true; data?: { document: DocumentResult } }>(`${API_BASE}/documents/${documentId}`);
    return res?.data?.document ?? null;
  },

  deleteDocument: async (documentId: string): Promise<boolean> => {
    const res = await del<{ ok: true }>(`${API_BASE}/documents/${documentId}`);
    return !!res?.ok;
  },

  getBrandProfile: async (): Promise<BrandProfile | null> => {
    const res = await get<{ ok: true; data?: { profile: BrandProfile | null } }>(`${API_BASE}/brand/profile`);
    return res?.data?.profile ?? null;
  },

  saveBrandProfile: async (profile: BrandProfile): Promise<BrandProfile | null> => {
    const res = await fetch(`${API_BASE}/brand/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!res.ok) {
      console.warn(`[api] save brand profile failed: ${res.status}`, await res.text());
      return null;
    }
    const json = (await res.json()) as { ok: true; data?: { profile: BrandProfile } };
    return json.data?.profile ?? null;
  },

  connectTelegram: async (payload: TelegramConnectPayload): Promise<BrandProfile | null> => {
    const res = await fetch(`${API_BASE}/brand/telegram/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      console.warn(`[api] telegram connect failed: ${res.status}`, await res.text());
      return null;
    }
    const json = (await res.json()) as { ok: true; data?: { profile: BrandProfile } };
    return json.data?.profile ?? null;
  },

  // ── Entity Suggestions ──
  listEntitySuggestions: async (status: string = "pending"): Promise<EntitySuggestion[]> => {
    const res = await get<{ ok: true; data?: { suggestions: EntitySuggestion[] } }>(
      `${API_BASE}/rag/suggestions?status=${status}`
    );
    return res?.data?.suggestions ?? [];
  },

  approveEntitySuggestion: async (id: string): Promise<boolean> => {
    const res = await post<{ ok: true }>(`${API_BASE}/rag/suggestions/${id}/approve`, {});
    return !!res?.ok;
  },

  ignoreEntitySuggestion: async (id: string): Promise<boolean> => {
    const res = await post<{ ok: true }>(`${API_BASE}/rag/suggestions/${id}/ignore`, {});
    return !!res?.ok;
  },

  // ── Brand Reference Images ──
  listReferenceImages: async (): Promise<ReferenceImage[]> => {
    const res = await get<{ ok: true; data?: { reference_images: ReferenceImage[] } }>(
      `${API_BASE}/rag/reference-images`
    );
    return res?.data?.reference_images ?? [];
  },

  uploadReferenceImage: async (
    file: File,
    linkedToType: string,
    linkedToName: string
  ): Promise<ReferenceImage | null> => {
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      form.append("linked_to_type", linkedToType);
      form.append("linked_to_name", linkedToName);

      const res = await fetch(`${API_BASE}/rag/reference-images/upload`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        console.warn(`[api] upload reference image failed: ${res.status}`, await res.text());
        return null;
      }
      const json = (await res.json()) as { ok: true; data?: { reference_image: ReferenceImage } };
      return json?.data?.reference_image ?? null;
    } catch (err) {
      console.warn("[api] upload reference image error", err);
      return null;
    }
  },

  runNow: (payload: RunNowPayload) =>
    post<{ ok: true; data?: { run_id: string } }>(RUN_URL, payload),

  /**
   * Conversational entry-point for the web modal. Sends source (research or
   * user_topic) and image_mode (text_only / with_image / mix); backend
   * threads both into the graph state and returns the run_id.
   */
  runDraft: (payload: {
    source: "research" | "user_topic";
    user_topic?: string;
    image_mode: "text_only" | "with_image" | "mix";
    country_scope?: "global" | "india";
    platforms?: Array<"linkedin">;
  }) =>
    post<{ ok: true; data?: { run_id: string } }>(
      `${API_BASE}/runs/chat`,
      payload,
    ),

  /** Free-form Regenerate: stores feedback in agent_logs then resumes. */
  regenerateWithFeedback: (runId: string, feedback: string) =>
    post<{ ok: true; data?: { run_id: string } }>(
      `${API_BASE}/runs/${runId}/regenerate-feedback`,
      { feedback },
    ),

  /** Idea selection action: picks 1, 2, 3, "all", "1,2", or "dismiss" */
  pickIdeas: (runId: string, choice: string, decidedBy: string = "web_modal") =>
    post<{ ok: true; data?: any }>(
      `${API_BASE}/runs/${runId}/idea-action`,
      { choice, decided_by: decidedBy },
    ),

  listResearch: async () => {
    const res = await get<{ ok: true; data?: { insights: any[] } }>(`${API_BASE}/research`);
    return res?.data?.insights ?? [];
  },

  runResearch: async (topic?: string, countryScope: "global" | "india" = "global"): Promise<ResearchRunResult | null> => {
    const res = await post<{ ok: true; data?: ResearchRunResult }>(`${API_BASE}/research/run`, {
      topic,
      country_scope: countryScope,
      platforms: ["instagram", "linkedin"],
    });
    return res?.data ?? null;
  },

  approvalAction: (runId: string, payload: ApprovalAction) => {
    const url = `${RUN_URL}/${runId}/approval`;
    return post<{ ok: true }>(url, payload);
  },

  deleteDraft: (runId: string, draftId: string) => {
    const url = `${RUN_URL}/${runId}/drafts/${draftId}`;
    return del<{ ok: true }>(url);
  },

  ragChat: async (question: string, documentId?: string): Promise<RagChatResult | null> => {
    const res = await post<{ ok: true; data?: RagChatResult }>(`${API_BASE}/rag/chat`, {
      question,
      document_id: documentId,
    });
    return res?.data ?? null;
  },
};

// Backwards compatibility alias for components during migration
export const n8n = api;
