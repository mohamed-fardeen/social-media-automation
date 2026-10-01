"use client";

import { useEffect, useState } from "react";
import { Check, RefreshCcw, Bot, MessageCircle, Send, Plus, Trash2, ShieldAlert, Camera, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { api, type BrandProfile, type ProductOneLiner, type ProjectOneLiner } from "@/lib/api";
import { getStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const defaultProducts: ProductOneLiner[] = [
  { name: "ATOM", one_liner: "Compact polar-based construction 3D-printing robot." },
  { name: "ATON", one_liner: "Large-format construction 3D-printing robot." },
  { name: "G.MINI", one_liner: "Compact laboratory/research 3D concrete printer." }
];

const defaultProjects: ProjectOneLiner[] = [
  { name: "MES Projects", one_liner: "Defense/security infrastructure — Guard Rooms, Sentry Posts, Runway infrastructure." },
  { name: "GCC Bus-Stop Project", one_liner: "3D-printed urban public transport bus shelter for municipal infrastructure." },
  { name: "ZOHO Project", one_liner: "Off-site and on-site sustainable 3D-printed architectural elements for corporate campus." },
  { name: "THE ARC", one_liner: "Large-span curved architectural showcase built with robotic precision printing." }
];

const emptyProfile: BrandProfile = {
  company_name: "Kelvin6k",
  website: "https://www.kelvin6k.com/",
  industry: "Construction 3D Printing / 3D Concrete Printing / Robotic Construction",
  target_audience: "Construction 3D-printing companies, large-scale 3D concrete printing manufacturers, construction 3D-printing engineers, robotics engineers developing 3D-printing systems, concrete and printable-material researchers, structural engineers working on 3D-printed structures, researchers developing 3D-printing techniques, and companies developing 3D-printing hardware, software, materials, and robotic systems for construction.",
  brand_voice: "Technical, engineering-focused, innovative, confident, practical, and future-oriented",
  brand_principle: "Real construction robotics deployed in real environments.",
  post_length: "medium",
  image_primary_provider: "openai",
  image_openai_model: "gpt-image-1-mini",
  image_openai_quality: "medium",
  competitors: ["ICON", "COBOD", "PERI 3D Construction Printing", "Apis Cor", "SQ4D", "CyBe Construction", "WASP", "Contour Crafting"],
  products: defaultProducts,
  projects: defaultProjects,
  hard_constraints: {
    never_invent: [
      "Projects", "Clients", "Product specifications", "Product prices",
      "Performance claims", "Cost savings", "Time savings", "Material savings",
      "Founder experiences", "Founder opinions", "Awards", "Certifications",
      "Partnerships", "Project dates", "Project locations", "Machine capabilities"
    ],
    product_naming: [
      "Preserve ATON and ATOM as separate names.",
      "Do not silently merge product specifications.",
      "Use the exact name associated with the source/reference being used."
    ],
    unknown_handling: "If the source does not establish a fact, mark it as unknown and do not guess."
  },
  approval_channel: "none",
  telegram_bot_token: "",
  telegram_chat_id: "",
  telegram_webhook_secret: "",
};

export default function SettingsPage() {
  const [profile, setProfile] = useState<BrandProfile>(emptyProfile);
  const [competitorsStr, setCompetitorsStr] = useState("");
  const [neverInventStr, setNeverInventStr] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [telegramStatus, setTelegramStatus] = useState<"idle" | "saving" | "connected" | "error">("idle");
  const [uploadingProductIdx, setUploadingProductIdx] = useState<number | null>(null);
  const [uploadingProjectIdx, setUploadingProjectIdx] = useState<number | null>(null);
  
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: "product" | "project", name: string, idx: number) => {
    if (!name.trim()) {
      alert("Please enter a name before uploading an image.");
      return;
    }
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (type === "product") setUploadingProductIdx(idx);
    else setUploadingProjectIdx(idx);
    
    try {
      const res = await api.uploadReferenceImage(file, type, name);
      if (res) {
        // Successfully uploaded. 
        // We don't necessarily need to store images in the profile state, 
        // because they are fetched dynamically via knowledge base RAG, 
        // but we can alert the user it was successful.
        alert(`Successfully uploaded reference image for ${name}!`);
      } else {
        alert(`Failed to upload reference image for ${name}.`);
      }
    } finally {
      if (type === "product") setUploadingProductIdx(null);
      else setUploadingProjectIdx(null);
      if (e.target) e.target.value = "";
    }
  };

  useEffect(() => {
    api.getBrandProfile().then((saved) => {
      if (!saved) return;
      const merged: BrandProfile = {
        ...emptyProfile,
        ...saved,
        products: saved.products && saved.products.length > 0 ? saved.products : defaultProducts,
        projects: saved.projects && saved.projects.length > 0 ? saved.projects : defaultProjects,
        hard_constraints: saved.hard_constraints || emptyProfile.hard_constraints
      };
      setProfile(merged);
      setCompetitorsStr((merged.competitors || []).join(", "));
      setNeverInventStr((merged.hard_constraints?.never_invent || []).join(", "));
      getStore().updateBrand(merged as any);
    });
  }, []);

  const update = <K extends keyof BrandProfile>(key: K, value: BrandProfile[K]) => {
    setProfile((current) => ({ ...current, [key]: value }));
  };

  const handleProductChange = (index: number, field: "name" | "one_liner", value: string) => {
    const list = [...(profile.products || [])];
    list[index] = { ...list[index], [field]: value };
    update("products", list);
  };

  const addProduct = () => {
    const list = [...(profile.products || []), { name: "", one_liner: "" }];
    update("products", list);
  };

  const removeProduct = (index: number) => {
    const list = (profile.products || []).filter((_, i) => i !== index);
    update("products", list);
  };

  const handleProjectChange = (index: number, field: "name" | "one_liner", value: string) => {
    const list = [...(profile.projects || [])];
    list[index] = { ...list[index], [field]: value };
    update("projects", list);
  };

  const addProject = () => {
    const list = [...(profile.projects || []), { name: "", one_liner: "" }];
    update("projects", list);
  };

  const removeProject = (index: number) => {
    const list = (profile.projects || []).filter((_, i) => i !== index);
    update("projects", list);
  };

  const save = async () => {
    setStatus("saving");
    const payload: BrandProfile = {
      ...profile,
      competitors: splitList(competitorsStr),
      hard_constraints: {
        ...(profile.hard_constraints || emptyProfile.hard_constraints!),
        never_invent: splitList(neverInventStr),
      },
    };
    const saved = await api.saveBrandProfile(payload);
    if (!saved) {
      setStatus("error");
      return;
    }
    setProfile({ ...emptyProfile, ...saved });
    getStore().updateBrand(saved as any);
    setStatus("saved");
    window.setTimeout(() => setStatus("idle"), 1800);
  };

  const configureTelegram = async () => {
    setTelegramStatus("saving");
    const saved = await api.connectTelegram({
      telegram_bot_token: profile.telegram_bot_token || "",
      telegram_chat_id: profile.telegram_chat_id || "",
      telegram_webhook_secret: profile.telegram_webhook_secret || "",
      approval_channel: "telegram",
    });
    if (!saved) {
      setTelegramStatus("error");
      return;
    }
    const next: BrandProfile = {
      ...profile,
      ...saved,
      approval_channel: "telegram",
    };
    setProfile(next);
    getStore().updateBrand(next as any);
    setTelegramStatus("connected");
    window.setTimeout(() => setTelegramStatus("idle"), 2200);
  };

  const canSave = profile.company_name.trim() && profile.industry.trim() && profile.target_audience.trim();

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Company setup"
        title="Brand Profile & Knowledge Base"
        description="Core identity, approved products, and verified project registries. Product specs and project facts live in vector retrieval; this profile provides standing identity."
        actions={
          <Button
            variant="primary"
            disabled={!canSave || status === "saving"}
            onClick={save}
            iconLeft={status === "saved" ? <Check className="h-3.5 w-3.5" /> : <RefreshCcw className="h-3.5 w-3.5" />}
          >
            {status === "saving" ? "Saving" : status === "saved" ? "Saved" : "Save Brand Profile"}
          </Button>
        }
      />

      {status === "error" && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          Could not save brand profile. Please check connection and try again.
        </div>
      )}

      {/* 1. Core Identity */}
      <section className="grid grid-cols-12 gap-6">
        <Header title="Identity & Positioning" hint="Standing voice and audience definitions injected into every editorial run." />
        <div className="col-span-12 grid grid-cols-1 gap-4 lg:col-span-9 md:grid-cols-2">
          <Field label="Company name" required>
            <input value={profile.company_name} onChange={(e) => update("company_name", e.target.value)} className="input" />
          </Field>
          <Field label="Website" optional>
            <input value={profile.website || ""} onChange={(e) => update("website", e.target.value)} className="input" placeholder="https://..." />
          </Field>
          <Field label="Industry" required full>
            <input value={profile.industry} onChange={(e) => update("industry", e.target.value)} className="input" />
          </Field>
          <Field label="Brand Principle" optional full>
            <input value={profile.brand_principle || ""} onChange={(e) => update("brand_principle", e.target.value)} className="input" placeholder="Real construction robotics deployed in real environments." />
          </Field>
          <Field label="Brand Voice" optional full>
            <textarea value={profile.brand_voice || ""} onChange={(e) => update("brand_voice", e.target.value)} rows={2} className="input" />
          </Field>
          <Field label="Target Audience" required full>
            <textarea value={profile.target_audience} onChange={(e) => update("target_audience", e.target.value)} rows={3} className="input" />
          </Field>
          <Field label="Competitors" optional full>
            <input value={competitorsStr} onChange={(e) => setCompetitorsStr(e.target.value)} className="input" placeholder="ICON, COBOD, PERI 3D..." />
          </Field>
          <Field label="Post Length" required>
            <select
              value={profile.post_length || "medium"}
              onChange={(e) => update("post_length", e.target.value as any)}
              className="input bg-ink-950 appearance-none"
            >
              <option value="short">Short (punchy, 50-80 words)</option>
              <option value="medium">Medium (standard, 100-150 words)</option>
              <option value="long">Long (deep-dive, 200+ words)</option>
            </select>
          </Field>
          <div className="col-span-1 md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="LinkedIn Handle" optional>
              <input value={profile.linkedin_handle || ""} onChange={(e) => update("linkedin_handle", e.target.value)} className="input" placeholder="@company" />
            </Field>
            <Field label="Instagram Handle" optional>
              <input value={profile.instagram_handle || ""} onChange={(e) => update("instagram_handle", e.target.value)} className="input" placeholder="@company" />
            </Field>
          </div>
        </div>
      </section>

      {/* 2. Products Registry */}
      <section className="grid grid-cols-12 gap-6">
        <Header title="Products Registry" hint="Approved products and single-sentence descriptions. Detailed technical specs are retrieved dynamically from Knowledge Base RAG." />
        <div className="col-span-12 lg:col-span-9 space-y-3">
          {(profile.products || []).map((prod, idx) => (
            <div key={idx} className="flex flex-col md:flex-row items-start md:items-center gap-3 rounded-lg border border-ink-700 bg-ink-900/50 p-3">
              <div className="w-full md:w-1/4">
                <label className="text-[11px] font-mono uppercase text-ink-400 block mb-1">Product Name</label>
                <input
                  value={prod.name}
                  onChange={(e) => handleProductChange(idx, "name", e.target.value)}
                  className="input font-semibold text-sodium-400"
                  placeholder="e.g. ATOM"
                />
              </div>
              <div className="w-full md:flex-1">
                <label className="text-[11px] font-mono uppercase text-ink-400 block mb-1">Core Description (One-Liner)</label>
                <input
                  value={prod.one_liner}
                  onChange={(e) => handleProductChange(idx, "one_liner", e.target.value)}
                  className="input"
                  placeholder="Compact polar-based construction 3D-printing robot."
                />
              </div>
              <div className="flex items-center gap-1 self-end md:self-center mt-2 md:mt-5">
                <label 
                  className={cn(
                    "p-2 text-ink-400 transition cursor-pointer flex items-center justify-center rounded-md",
                    uploadingProductIdx === idx ? "text-ink-200" : "hover:text-sodium-400 hover:bg-ink-800"
                  )}
                  title="Upload reference image"
                >
                  {uploadingProductIdx === idx ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                  <input 
                    type="file" 
                    accept="image/*" 
                    className="hidden" 
                    onChange={(e) => handleImageUpload(e, "product", prod.name, idx)}
                    disabled={uploadingProductIdx === idx}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => removeProduct(idx)}
                  className="p-2 text-ink-400 hover:text-red-400 hover:bg-ink-800 transition rounded-md"
                  title="Remove product"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
          <Button variant="secondary" size="sm" onClick={addProduct} iconLeft={<Plus className="h-3.5 w-3.5" />}>
            Add Product
          </Button>
        </div>
      </section>

      {/* 3. Projects Registry */}
      <section className="grid grid-cols-12 gap-6">
        <Header title="Projects Registry" hint="Verified client and showcase builds. Detailed metrics are retrieved dynamically from Knowledge Base RAG." />
        <div className="col-span-12 lg:col-span-9 space-y-3">
          {(profile.projects || []).map((proj, idx) => (
            <div key={idx} className="flex flex-col md:flex-row items-start md:items-center gap-3 rounded-lg border border-ink-700 bg-ink-900/50 p-3">
              <div className="w-full md:w-1/4">
                <label className="text-[11px] font-mono uppercase text-ink-400 block mb-1">Project Name</label>
                <input
                  value={proj.name}
                  onChange={(e) => handleProjectChange(idx, "name", e.target.value)}
                  className="input font-semibold text-sodium-400"
                  placeholder="e.g. MES Projects"
                />
              </div>
              <div className="w-full md:flex-1">
                <label className="text-[11px] font-mono uppercase text-ink-400 block mb-1">Context & Summary (One-Liner)</label>
                <input
                  value={proj.one_liner}
                  onChange={(e) => handleProjectChange(idx, "one_liner", e.target.value)}
                  className="input"
                  placeholder="Defense/security infrastructure — Guard Rooms, Sentry Posts."
                />
              </div>
              <div className="flex items-center gap-1 self-end md:self-center mt-2 md:mt-5">
                <label 
                  className={cn(
                    "p-2 text-ink-400 transition cursor-pointer flex items-center justify-center rounded-md",
                    uploadingProjectIdx === idx ? "text-ink-200" : "hover:text-sodium-400 hover:bg-ink-800"
                  )}
                  title="Upload reference image"
                >
                  {uploadingProjectIdx === idx ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                  <input 
                    type="file" 
                    accept="image/*" 
                    className="hidden" 
                    onChange={(e) => handleImageUpload(e, "project", proj.name, idx)}
                    disabled={uploadingProjectIdx === idx}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => removeProject(idx)}
                  className="p-2 text-ink-400 hover:text-red-400 hover:bg-ink-800 transition rounded-md"
                  title="Remove project"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
          <Button variant="secondary" size="sm" onClick={addProject} iconLeft={<Plus className="h-3.5 w-3.5" />}>
            Add Project
          </Button>
        </div>
      </section>

      {/* 4. Hard Constraints */}
      <section className="grid grid-cols-12 gap-6">
        <Header title="Anti-Hallucination Guardrails" hint="Strict rules enforced across all agents to guarantee factual accuracy." />
        <div className="col-span-12 lg:col-span-9 rounded-lg border border-ink-700 bg-ink-900/40 p-4 space-y-4">
          <div className="flex items-center gap-2 text-sodium-400 font-mono text-xs uppercase tracking-wider">
            <ShieldAlert className="h-4 w-4" /> Hard Constraints
          </div>
          <Field label="Never Invent (Comma Separated)" required full>
            <input
              value={neverInventStr}
              onChange={(e) => setNeverInventStr(e.target.value)}
              className="input"
              placeholder="Projects, Clients, Product specifications, Prices, Performance claims..."
            />
          </Field>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Product Naming Constraints" optional full>
              <div className="p-3 bg-ink-950 rounded border border-ink-800 text-xs text-ink-300 space-y-1">
                <div>• Preserve ATON and ATOM as separate names.</div>
                <div>• Do not silently merge product specifications.</div>
                <div>• Use exact name associated with the source.</div>
              </div>
            </Field>
            <Field label="Unknown Handling" optional full>
              <div className="p-3 bg-ink-950 rounded border border-ink-800 text-xs text-ink-300">
                If the source does not establish a fact, mark it as unknown and do not guess.
              </div>
            </Field>
          </div>
        </div>
      </section>

      {/* 5. Image Generation */}
      <section className="grid grid-cols-12 gap-6">
        <Header title="Image Generation" hint="Configure models, providers, and quality for visual post generation." />
        <div className="col-span-12 lg:col-span-9 rounded-lg border border-ink-700 bg-ink-900/40 p-4 space-y-4">
          <Field label="Primary Provider" required>
            <select
              value={profile.image_primary_provider || "openai"}
              onChange={(e) => update("image_primary_provider", e.target.value as any)}
              className="input bg-ink-950 appearance-none"
            >
              <option value="openai">OpenAI (Gemini as fallback)</option>
              <option value="gemini">Google Gemini (OpenAI as fallback)</option>
            </select>
          </Field>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="OpenAI Model" required>
              <select
                value={profile.image_openai_model || "gpt-image-1-mini"}
                onChange={(e) => update("image_openai_model", e.target.value)}
                className="input bg-ink-950 appearance-none"
              >
                <option value="gpt-image-2">GPT Image 2 (Flagship)</option>
                <option value="gpt-image-1.5">GPT Image 1.5</option>
                <option value="gpt-image-1">GPT Image 1</option>
                <option value="gpt-image-1-mini">GPT Image 1 Mini (Fast/Cheap)</option>
              </select>
            </Field>
            <Field label="OpenAI Quality" required>
              <select
                value={profile.image_openai_quality || "medium"}
                onChange={(e) => update("image_openai_quality", e.target.value as any)}
                className="input bg-ink-950 appearance-none"
              >
                <option value="low">Low (Fastest)</option>
                <option value="medium">Medium (Standard)</option>
                <option value="high">High (Best Detail)</option>
              </select>
            </Field>
          </div>
        </div>
      </section>

      {/* 6. Telegram Approval */}
      <section className="grid grid-cols-12 gap-6">
        <Header title="Approval connection" hint="Pick the channel that receives draft approvals." />
        <div className="col-span-12 lg:col-span-9 space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <ConnectionCard
              icon={<Bot className="h-5 w-5" />}
              title="Telegram"
              description="Send drafts to a Telegram bot and approve, regenerate, or dismiss from chat."
              selected={profile.approval_channel === "telegram"}
              onClick={() => update("approval_channel", "telegram")}
            />
            <ConnectionCard
              icon={<MessageCircle className="h-5 w-5" />}
              title="WhatsApp"
              description="Not enabled in this build."
              selected={false}
              disabled
            />
          </div>

          {profile.approval_channel === "telegram" && (
            <div className="rounded-lg border border-ink-600 bg-ink-900/40 p-4">
              <div className="mb-4 flex items-center gap-2">
                <Send className="h-4 w-4 text-sodium-500" />
                <div>
                  <div className="font-mono text-xs uppercase tracking-wider text-ink-200">Telegram setup</div>
                  <p className="text-sm text-ink-300">Use the bot token from BotFather once. After that, the bot handles approvals and commands automatically.</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Field label="Bot token" required>
                  <input value={profile.telegram_bot_token || ""} onChange={(e) => update("telegram_bot_token", e.target.value)} className="input" placeholder="123456:ABC..." />
                </Field>
                <Field label="Chat ID" required>
                  <input value={profile.telegram_chat_id || ""} onChange={(e) => update("telegram_chat_id", e.target.value)} className="input" placeholder="Telegram chat or group id" />
                </Field>
                <Field label="Webhook secret" optional full>
                  <input value={profile.telegram_webhook_secret || ""} onChange={(e) => update("telegram_webhook_secret", e.target.value)} className="input" placeholder="Optional secret for webhook verification" />
                </Field>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <Button
                  variant="primary"
                  onClick={configureTelegram}
                  disabled={!profile.telegram_bot_token || !profile.telegram_chat_id || telegramStatus === "saving"}
                  iconLeft={<Bot className="h-3.5 w-3.5" />}
                >
                  {telegramStatus === "saving" ? "Connecting" : telegramStatus === "connected" ? "Connected" : "Configure Telegram"}
                </Button>
                <span className="text-xs text-ink-400">
                  This saves the bot and sends a confirmation message to Telegram.
                </span>
              </div>
              {telegramStatus === "error" && (
                <div className="mt-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-100">
                  Telegram configuration failed. Check the bot token, chat ID, and that the bot has been started in Telegram.
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <style jsx>{`
        .input {
          width: 100%;
          background: #131417;
          border: 1px solid #23252b;
          border-radius: 6px;
          padding: 9px 10px;
          font-size: 13px;
          color: #edeef0;
          outline: none;
        }
        .input:focus {
          border-color: #f5b947;
        }
      `}</style>
    </div>
  );
}

function splitList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function Header({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="col-span-12 lg:col-span-3">
      <h2 className="text-sm font-semibold text-ink-100">{title}</h2>
      <p className="mt-1 text-xs text-ink-400 leading-relaxed">{hint}</p>
    </div>
  );
}

function Field({
  label,
  children,
  required,
  optional,
  full,
}: {
  label: string;
  children: React.ReactNode;
  required?: boolean;
  optional?: boolean;
  full?: boolean;
}) {
  return (
    <div className={`space-y-1.5 ${full ? "md:col-span-2" : ""}`}>
      <label className="flex items-center justify-between text-xs font-medium text-ink-300">
        <span>{label}</span>
        {required && <span className="font-mono text-[10px] uppercase text-sodium-500">Required</span>}
        {optional && <span className="text-[10px] text-ink-500">Optional</span>}
      </label>
      {children}
    </div>
  );
}

function ConnectionCard({
  icon,
  title,
  description,
  selected,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  selected: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`relative flex items-start gap-3 rounded-lg border p-4 text-left transition ${
        disabled
          ? "cursor-not-allowed border-ink-800 bg-ink-950/30 opacity-50"
          : selected
            ? "border-sodium-500/80 bg-sodium-500/10 shadow-sm"
            : "border-ink-700 bg-ink-900/40 hover:border-ink-500"
      }`}
    >
      <div className={`mt-0.5 rounded-md p-1.5 ${selected ? "bg-sodium-500/20 text-sodium-400" : "bg-ink-800 text-ink-300"}`}>
        {icon}
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink-100">{title}</span>
          {selected && <span className="rounded-full bg-sodium-500/20 px-1.5 py-0.5 font-mono text-[9px] uppercase text-sodium-300">Active</span>}
        </div>
        <p className="mt-1 text-xs text-ink-400 leading-relaxed">{description}</p>
      </div>
    </button>
  );
}
