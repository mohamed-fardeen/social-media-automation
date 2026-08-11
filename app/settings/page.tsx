"use client";

import { useState } from "react";
import { useBrand } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { StatusDot } from "@/components/ui/StatusDot";
import { Check, X, Plus, RefreshCcw, Eye, EyeOff } from "lucide-react";

export default function SettingsPage() {
  const brand = useBrand();
  const [saved, setSaved] = useState(false);
  const [showKeys, setShowKeys] = useState(false);

  // Mirror brand into local state so the form is editable
  const [name, setName] = useState(brand.name);
  const [industry, setIndustry] = useState(brand.industry);
  const [voice, setVoice] = useState(brand.voice);
  const [audience, setAudience] = useState(brand.audience);
  const [competitors, setCompetitors] = useState(brand.competitors.join(", "));
  const [model, setModel] = useState(brand.model);
  const [igHandle, setIgHandle] = useState(brand.ig_handle ?? "");
  const [liHandle, setLiHandle] = useState(brand.li_handle ?? "");

  function save() {
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Settings"
        title="Configure the engine."
        description="Brand context, audience, model choice, and integration status. Nothing here leaves the browser."
        actions={
          <Button variant="primary" onClick={save} iconLeft={saved ? <Check className="h-3.5 w-3.5" /> : undefined}>
            {saved ? "Saved" : "Save changes"}
          </Button>
        }
      />

      {/* Brand */}
      <section className="grid grid-cols-12 gap-6">
        <Header2 number="01" title="Brand" hint="The strategist & copywriter read this verbatim." />
        <div className="col-span-12 lg:col-span-9 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} className="input" />
          </Field>
          <Field label="Industry">
            <input value={industry} onChange={(e) => setIndustry(e.target.value)} className="input" />
          </Field>
          <Field label="Instagram handle" prefix="@">
            <input value={igHandle} onChange={(e) => setIgHandle(e.target.value)} className="input" />
          </Field>
          <Field label="LinkedIn handle" prefix="@">
            <input value={liHandle} onChange={(e) => setLiHandle(e.target.value)} className="input" />
          </Field>
          <Field label="Brand voice" full>
            <textarea value={voice} onChange={(e) => setVoice(e.target.value)} rows={4} className="input" />
          </Field>
          <Field label="Target audience" full>
            <textarea value={audience} onChange={(e) => setAudience(e.target.value)} rows={3} className="input" />
          </Field>
          <Field label="Competitors" full>
            <input value={competitors} onChange={(e) => setCompetitors(e.target.value)} className="input" placeholder="Linear, Height, Notion" />
          </Field>
        </div>
      </section>

      {/* AI model */}
      <section className="grid grid-cols-12 gap-6">
        <Header2 number="02" title="AI model" hint="Primary creative model used by Strategist & Copywriter." />
        <div className="col-span-12 lg:col-span-9 space-y-3">
          <Field label="Primary model">
            <select value={model} onChange={(e) => setModel(e.target.value)} className="input">
              <option value="grok-4">grok-4 — best reasoning, slower</option>
              <option value="grok-4-fast">grok-4-fast — fast, cheaper</option>
              <option value="grok-4-vision">grok-4-vision — visual reasoning</option>
            </select>
          </Field>
          <p className="text-xs text-ink-300 leading-relaxed max-w-prose">
            Keys are never sent to the browser. All model calls are mediated by n8n, where credentials live server-side.
          </p>
        </div>
      </section>

      {/* Integrations */}
      <section className="grid grid-cols-12 gap-6">
        <Header2 number="03" title="Integrations" hint="Connection status to the systems behind the agent swarm." />
        <div className="col-span-12 lg:col-span-9 grid grid-cols-1 md:grid-cols-2 gap-px bg-ink-600 border border-ink-600 rounded-lg overflow-hidden">
          <Integration
            name="Supabase"
            detail="Database · Storage · Realtime"
            status="connected"
            meta="Project: kelvin6k-prod"
          />
          <Integration
            name="n8n"
            detail="Workflow orchestration"
            status="connected"
            meta="Workflows: 6 active"
          />
          <Integration
            name="xAI (Grok)"
            detail="LLM for all agents"
            status="connected"
            meta="Server-side only"
          />
          <Integration
            name="Instagram Graph"
            detail="Publishing"
            status="connected"
            meta={brand.ig_handle ?? "@atlas"}
          />
          <Integration
            name="LinkedIn API"
            detail="Publishing"
            status="connected"
            meta={brand.li_handle ?? "atlas-run"}
          />
          <Integration
            name="Apify"
            detail="Competitor scrape"
            status="connected"
            meta="Server-side only"
          />
          <Integration
            name="Tavily"
            detail="Research"
            status="connected"
            meta="Server-side only"
          />
          <Integration
            name="Flux"
            detail="Image generation"
            status="connected"
            meta="flux-pro-1.1"
          />
        </div>
        <p className="col-span-12 lg:col-span-9 lg:col-start-4 -mt-3 text-xs text-ink-300 leading-relaxed">
          Sensitive credentials live in n8n. The browser only sees an opaque webhook URL.
        </p>
      </section>

      {/* Webhook */}
      <section className="grid grid-cols-12 gap-6">
        <Header2 number="04" title="Webhooks" hint="Endpoints the frontend calls. Configured via env." />
        <div className="col-span-12 lg:col-span-9 space-y-3">
          <Field label="Base URL">
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={(typeof window !== "undefined" && process.env.NEXT_PUBLIC_N8N_BASE) || "Set NEXT_PUBLIC_N8N_BASE in .env.local"}
                className="input font-mono text-xs"
              />
              <Button variant="outline" size="sm" iconLeft={showKeys ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />} onClick={() => setShowKeys((s) => !s)}>
                {showKeys ? "Hide" : "Show"}
              </Button>
            </div>
          </Field>
          <EndPoints />
        </div>
      </section>

      <style jsx>{`
        .input {
          width: 100%;
          background: #131417;
          border: 1px solid #23252b;
          border-radius: 6px;
          padding: 8px 10px;
          font-size: 13px;
          color: #edeef0;
          outline: none;
        }
        .input:focus {
          border-color: #3a3d46;
        }
      `}</style>
    </div>
  );
}

function Field({ label, children, full, prefix }: { label: string; children: React.ReactNode; full?: boolean; prefix?: string }) {
  return (
    <label className={"block " + (full ? "md:col-span-2" : "")}>
      <span className="font-mono text-2xs uppercase tracking-wider text-ink-300">{label}</span>
      <div className="mt-1.5 flex items-center gap-2">
        {prefix && <span className="text-ink-300 font-mono text-sm">{prefix}</span>}
        {children}
      </div>
    </label>
  );
}

function Header2({ number, title, hint }: { number: string; title: string; hint: string }) {
  return (
    <div className="col-span-12 lg:col-span-3">
      <div className="font-mono text-2xs uppercase tracking-wider text-sodium-500">{number}</div>
      <h2 className="mt-1.5 font-display text-xl font-medium text-ink-50">{title}</h2>
      <p className="mt-1 text-sm text-ink-200">{hint}</p>
    </div>
  );
}

function Integration({
  name,
  detail,
  status,
  meta,
}: {
  name: string;
  detail: string;
  status: "connected" | "pending" | "error";
  meta: string;
}) {
  return (
    <div className="bg-ink-900 px-4 py-3.5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-ink-50">{name}</div>
          <div className="font-mono text-2xs text-ink-300">{detail}</div>
        </div>
        <StatusDot status={status === "connected" ? "live" : status === "pending" ? "pending" : "failed"} withLabel />
      </div>
      <div className="mt-2 font-mono text-2xs text-ink-200 truncate">{meta}</div>
    </div>
  );
}

function EndPoints() {
  const routes = [
    { path: "/webhook/kelvin6k/ingest", method: "POST", desc: "Document & URL ingestion" },
    { path: "/webhook/kelvin6k/run-now", method: "POST", desc: "Trigger a generation pipeline" },
    { path: "/webhook/kelvin6k/approval-action", method: "POST", desc: "Approve / reject / regenerate" },
  ];
  return (
    <ul className="rounded-lg border border-ink-600 overflow-hidden">
      {routes.map((r) => (
        <li key={r.path} className="grid grid-cols-12 gap-3 px-4 py-2.5 border-b border-ink-600 last:border-0 items-center bg-ink-900">
          <div className="col-span-2 font-mono text-2xs text-ink-200">{r.method}</div>
          <div className="col-span-6 font-mono text-xs text-sodium-500 truncate">{r.path}</div>
          <div className="col-span-4 text-xs text-ink-300">{r.desc}</div>
        </li>
      ))}
    </ul>
  );
}
