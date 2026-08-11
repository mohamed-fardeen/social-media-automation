# Kelvin6k — AI Social Engine

A premium, dark, cinematic command center for AI-driven social media. Built for the Kelvin6k pipeline that orchestrates **Supabase** (database, storage, realtime), **n8n** (workflow orchestration), **xAI Grok** (agents), and **Instagram + LinkedIn** (publishing).

## What's inside

- **Command Center** — today's generated posts, live AI agent timeline, one-click approval.
- **Content Studio** — full post editor with live Instagram + LinkedIn previews, version history, and regeneration feedback.
- **AI Agents** — six specialized agents (Strategist, Research, Copywriter, Visual, Knowledge/RAG, Publisher) with execution history.
- **Knowledge Base** — drag-and-drop document upload to Supabase Storage with auto-chunking and embedding.
- **Research** — industry trends, competitor signals, and AI recommendations with "Generate content" actions.
- **Content Calendar** — month / week / list views of scheduled and published posts.
- **Analytics** — engagement, approval rate, regen rate, platform split, top posts.
- **Settings** — brand information, audience, voice, competitors, model, integration status.

The core flow is enforced everywhere:

> **Knowledge → Research → AI Agents → Content → Human Approval → Publish → Analytics**

## Stack

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS — custom token system (deep charcoal + sodium-amber accent)
- Framer Motion — orchestrated micro-interactions
- Supabase JS — database, storage, realtime
- Recharts — analytics
- Lucide — icons
- Inter, Inter Tight, JetBrains Mono, Instrument Serif — typography

## Getting started

```bash
# 1. Install
npm install

# 2. Copy the env template and edit (optional)
cp .env.example .env.local

# 3. Run
npm run dev
```

The app runs in **MOCK mode** without env vars — it serves rich seeded data and simulates the agent pipeline so you can tour every page. Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_N8N_BASE` to wire the real backend.

## Scripts

```bash
npm run dev        # Dev server
npm run build      # Production build
npm run start      # Production server
npm run lint       # Lint
npm run typecheck  # Type check
```

## Supabase schema

The frontend reads these tables (the schema lives in your Supabase project):

- `documents` — uploaded brand/knowledge artifacts
- `knowledge_chunks` — embedded chunks of those documents (RAG)
- `post_runs` — agent pipeline runs
- `post_drafts` — generated posts (caption, hashtags, image, status)
- `agent_logs` — every agent's input/output and latency
- `publish_results` — what the publisher actually did

Realtime channels subscribe to `post_drafts`, `post_runs`, and `agent_logs` for live updates.

## n8n webhooks

The browser calls these public endpoints:

- `POST /webhook/kelvin6k/ingest` — document / URL / note ingestion
- `POST /webhook/kelvin6k/run-now` — trigger a generation pipeline
- `POST /webhook/kelvin6k/approval-action` — approve / reject / regenerate

All API keys (Grok, Apify, Tavily, Instagram, LinkedIn, Flux) live in n8n credentials. The browser never sees them.

## Design notes

The aesthetic is intentional: deep charcoal (`#0A0B0D`), sodium-amber accent (`#F5B947`), editorial typography. The signature element is the **live agent timeline** — every stage of the pipeline shows the agent, model, latency, and a snippet of what it just produced. Nothing is a placeholder spinner.

## Project structure

```
app/                  # Next.js App Router pages
components/
  layout/             # Sidebar, Topbar, PageHeader
  ui/                 # Button, StatusDot, PlatformIcon, Chip, etc.
  timeline/           # AgentTimeline (the signature)
  post-preview/       # InstagramPreview, LinkedInPreview
  BootstrapRealtime.tsx
hooks/                # (extensible)
lib/
  supabase.ts         # Client + realtime
  n8n.ts              # Webhook wrappers
  types.ts            # Domain types matching DB schema
  mock-data.ts        # Rich seeded data
  store.ts            # Reactive store (Realtime + mock) + simulator
  utils.ts            # cn, formatters
```
