# Kelvin6k AI Social Engine V2

Production-ready backend and Next.js frontend for **Kelvin6k AI Social Engine**.

## Architecture Overview

```text
Frontend (Next.js 14)
       │
       ▼
FastAPI Backend (Python)
       │
       ▼
LangGraph Swarm
 ├── Research Agent (Tavily)
 ├── Knowledge Agent (Supabase pgvector)
 ├── Strategist Agent (xAI Grok)
 ├── Copywriter Agent (xAI Grok)
 ├── Visual Agent (xAI Grok)
 └── Publisher Agent (Instagram & LinkedIn)
       │
       ▼
Supabase PostgreSQL / Storage / Realtime
```

## Directory Structure

* [`frontend/`](file:///c:/Users/Abdullah/Documents/Social%20Media%20Automation/frontend) — Next.js 14 App Router UI
* [`backend/`](file:///c:/Users/Abdullah/Documents/Social%20Media%20Automation/backend) — FastAPI + LangGraph Python backend

## Running the Project

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger API documentation will be available at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm run dev
```

The UI will be running at `http://localhost:3000`.
