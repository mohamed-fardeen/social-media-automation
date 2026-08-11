// Thin wrappers around the n8n webhooks. Never expose secret keys here.
// All keys live server-side in n8n credentials; the frontend only sends
// opaque payloads.

const INGEST_URL = process.env.NEXT_PUBLIC_N8N_INGEST_URL || (process.env.NEXT_PUBLIC_N8N_BASE ? `${process.env.NEXT_PUBLIC_N8N_BASE}/webhook/kelvin6k/ingest` : "");
const RUN_URL = process.env.NEXT_PUBLIC_N8N_RUN_URL || (process.env.NEXT_PUBLIC_N8N_BASE ? `${process.env.NEXT_PUBLIC_N8N_BASE}/webhook/kelvin6k/run-now` : "");
const APPROVAL_URL = process.env.NEXT_PUBLIC_N8N_APPROVAL_URL || (process.env.NEXT_PUBLIC_N8N_BASE ? `${process.env.NEXT_PUBLIC_N8N_BASE}/webhook/kelvin6k/approval-action` : "");

export type IngestPayload = {
  source: "document" | "url" | "note";
  filename?: string;
  storage_path?: string;
  url?: string;
  text?: string;
  brand_id?: string;
};

export type RunNowPayload = {
  brand_id?: string;
  platforms?: Array<"instagram" | "linkedin">;
  topic?: string;
  notes?: string;
};

export type ApprovalAction = {
  draft_id: string;
  action: "approve" | "reject" | "regenerate";
  feedback?: string;
  decided_by?: string;
};

async function post<T>(url: string, body: unknown): Promise<T | null> {
  if (!url) {
    console.info(`[n8n mock] POST (no URL configured)`, body);
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
      console.warn(`[n8n] ${url} failed: ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[n8n] ${url} error`, err);
    return null;
  }
}

export const n8n = {
  ingest: (payload: IngestPayload) =>
    post<{ ok: true }>(INGEST_URL, payload),
  runNow: (payload: RunNowPayload) =>
    post<{ run_id: string }>(RUN_URL, payload),
  approvalAction: (payload: ApprovalAction) =>
    post<{ ok: true }>(APPROVAL_URL, payload),
};
