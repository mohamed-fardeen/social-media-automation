"""
Knowledge/RAG Agent — retrieves brand knowledge from Supabase pgvector and synthesizes connections to Kelvin6k.
Returns relevant chunks with source citations for downstream agents.
"""
import time
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.services.rag.store import KnowledgeStore
from app.services.brand_profile import format_brand_context, get_brand_profile
from app.config.logging import logger

KNOWLEDGE_SYSTEM_PROMPT = """You are a technical knowledge assistant for Kelvin6k.
Given the company profile and retrieved document chunks, analyze and synthesize them to answer:
"What existing Kelvin6k product, project, technology, capability, or brand context makes this research relevant?"

Prioritize real Kelvin6k information, specifically:
- ATON (robotic arm printer)
- ATOM (gantry or mobile printer)
- G.MINI (compact printer)
- ARCUS (robotic construction ecosystem)
- MES projects (e.g. Guard Room, Sentry Post, runway off-site)
- GCC bus-stop project
- ZOHO project (green building)
- THE ARC (off-site printed space)

Strict Guidelines:
1. ONLY use information explicitly supported by the retrieved document chunks and company profile.
2. Do NOT invent, assume, or fabricate any connections, products, or projects when the knowledge base or profile does not support one.
3. If no clear connection is found, simply state: "No specific Kelvin6k product, project, or technology connection found in the retrieved knowledge base. The topic relates generally to the brand profile's industry context."
4. Be precise, technical, and direct. Avoid marketing fluff or exaggeration."""


def _update_run_progress(run_id: str, status: str, agent: str) -> None:
    """Best-effort update of post_runs.status + current_agent for frontend progress."""
    try:
        from app.database.supabase_client import get_supabase_client
        supa = get_supabase_client()
        if supa:
            supa.table("post_runs").update(
                {"status": status, "current_agent": agent}
            ).eq("id", run_id).execute()
    except Exception:
        pass  # non-fatal — never block the pipeline


def knowledge_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "knowledge", "running",
                             input_summary=f"topic: {state.get('topic', 'general')}")
    t0 = time.monotonic()
    _update_run_progress(run_id, "researching", "knowledge")

    try:
        store = KnowledgeStore()
        topic = state.get("topic") or state.get("topic_hint") or "business"
        brand_context = format_brand_context(get_brand_profile(state.get("brand_id") or "default"))

        chunks = store.similarity_search(
            query=topic,
            match_count=10,
            match_threshold=0.70
        )

        if chunks:
            context_parts = []
            citations = []
            for chunk in chunks[:6]:
                src_label = chunk.get("source_label") or "Knowledge Document"
                src_type = chunk.get("source_type") or "COMPANY_TRUTH"
                doc_id = chunk.get("document_id") or "doc"
                header = f"[{src_type}] Source: {src_label} (doc: {doc_id})"
                context_parts.append(f"{header}\n{chunk['content'][:600]}")
                if src_label and src_label not in citations:
                    citations.append(f"[{src_type}] {src_label}")

            # Only synthesize via LLM when we have real chunks worth connecting
            try:
                from app.services.llm.groq import GroqLLM
                llm = GroqLLM()
                chunks_text = "\n\n".join(context_parts)
                user_prompt = (
                    f"RETRIEVED KNOWLEDGE CHUNKS:\n{chunks_text}\n\n"
                    f"COMPANY PROFILE:\n{brand_context}\n\n"
                    f"TOPIC OF INTEREST:\n{topic}\n\n"
                    "Analyze the above inputs and answer: \"What existing Kelvin6k product, project, technology, "
                    "capability, or brand context makes this research relevant?\"\n"
                    "Remember to prioritize ATON, ATOM, G.MINI, ARCUS, MES projects, GCC bus-stop project, "
                    "ZOHO project, and THE ARC. Do not invent connections. Keep answer under 200 words."
                )
                synthesized_connection = llm.chat(
                    system_prompt=KNOWLEDGE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    max_tokens=400,   # keep it tight — this is a brief, not an essay
                )
            except Exception as e:
                logger.warning(f"[knowledge_node] LLM synthesis failed (non-fatal): {e}")
                synthesized_connection = f"Retrieved {len(chunks)} brand knowledge chunks."

            knowledge_context = (
                f"=== COMPANY PROFILE ===\n{brand_context}\n\n"
                f"=== SYNTHESIZED KELVIN6K CONNECTION ===\n{synthesized_connection}\n\n"
                f"=== RETRIEVED TRUTH CHUNKS ===\n" + "\n\n".join(context_parts)
            )

        else:
            # No RAG chunks found — skip the Groq call entirely.
            # Downstream agents already receive the full brand profile; adding an
            # LLM synthesis over an empty result just wastes 10-20 seconds.
            logger.info(f"[knowledge_node] Run {run_id}: no chunks found — using brand profile only.")
            knowledge_context = (
                f"COMPANY PROFILE:\n{brand_context}\n\n"
                "No specific document knowledge was found for this topic. "
                "Use the brand profile above and the research context from the research agent."
            )
            citations = []

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "knowledge", "complete",
                        output_summary=f"{len(chunks) if chunks else 0} chunks retrieved · {len(citations)} sources",
                        latency_ms=latency,
                        log_id=log_id)

        return {
            **state,
            "knowledge_context": knowledge_context,
            "knowledge_citations": citations,
        }

    except Exception as e:
        logger.error(f"Knowledge node failed for run {run_id}: {e}")
        log_agent_event(run_id, "knowledge", "error", error=str(e), log_id=log_id)
        return {
            **state,
            "knowledge_context": "No brand knowledge available.",
            "knowledge_citations": [],
            "errors": state.get("errors", []) + [f"knowledge: {e}"]
        }
