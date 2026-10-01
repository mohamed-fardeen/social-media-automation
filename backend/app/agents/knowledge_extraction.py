"""
Knowledge Extraction Agent
Bounded fact extractor that parses uploaded documents into atomic, self-contained
natural-language sentences for vector indexing and flags unknown brand entities
for human approval.
"""
import json
import re
from typing import Dict, Any, List, Optional
from app.services.llm.groq import GroqLLM
from app.services.llm.gemini import GeminiLLM
from app.services.rag.embedder import EmbeddingProvider
from app.services.brand_profile import get_brand_profile
from app.services.entity_suggestions import add_pending_suggestion
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT = """You are a factual knowledge extraction agent for a corporate knowledge base.
Given an uploaded document and a list of known brand entities, extract self-contained atomic facts.

Rules:
1. Extract facts into three categories:
   - product_truths: specs, configurations, capabilities of products
   - project_truths: details about specific builds, clients, structures
   - claims: industry benchmarks, research findings, market stats (must include numerical values)

2. Atomic chunk requirement:
   - Each fact must be ONE self-contained sentence.
   - Start the sentence with the explicit entity name (never "The robot", "It", "They").
   - Include the specific numbers, units, materials, or partner names.
   - Do not combine multiple unrelated facts into one sentence.

3. Entity check:
   - Check every extracted product and project against the provided known_entities list.
   - If a document mentions a product or project NOT in the known_entities list:
     - Do NOT add it to the Brand Profile.
     - DO extract facts about it.
     - Flag it in new_entity_suggestions with type ("product" | "project"), name, and a one-sentence context description.

Output format (strict JSON):
{
  "product_truths": [
    { "entity": "ATOM", "fact": "ATOM's base configuration weighs 550kg with a 5 x 3 meter build reach.", "type": "specification" }
  ],
  "project_truths": [
    { "entity": "MES Projects", "fact": "Kelvin6k built 3D-printed sentry posts for the Military Engineer Services.", "type": "project_detail" }
  ],
  "claims": [
    { "claim": "3D concrete printing reduces construction waste by up to 60% compared to conventional formwork.", "source_detail": "Page 4" }
  ],
  "new_entity_suggestions": [
    { "type": "product", "name": "VORTEX", "context": "Mentioned as a new mortar mixing system for continuous feed." }
  ]
}
"""


def extract_and_index_document_knowledge(
    document_id: str,
    document_text: str,
    source_filename: str = ""
) -> Dict[str, Any]:
    """Extract atomic facts from document_text, embed and insert them into knowledge_chunks,
    and register any unknown entity suggestions for human approval.
    """
    if not document_text or len(document_text.strip()) < 20:
        return {"chunks_indexed": 0, "suggestions_found": 0}

    # 1. Fetch known entities from Brand Profile
    profile = get_brand_profile()
    known_products = [p.get("name") for p in profile.get("products", []) if p.get("name")]
    known_projects = [p.get("name") for p in profile.get("projects", []) if p.get("name")]
    known_entities = {
        "products": known_products,
        "projects": known_projects
    }

    user_prompt = f"""=== KNOWN BRAND ENTITIES ===
Known Products: {', '.join(known_products) if known_products else 'None'}
Known Projects: {', '.join(known_projects) if known_projects else 'None'}

=== DOCUMENT CONTENT (Source: {source_filename or 'Uploaded File'}) ===
{document_text[:12000]}

Extract all atomic facts strictly following the system rules. Output pure JSON only."""

    llm = GroqLLM()
    extracted_data = {}
    try:
        raw_text = llm.chat(
            system_prompt=KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1
        )
        json_match = re.search(r"\{[\s\S]*\}", str(raw_text))
        if json_match:
            extracted_data = json.loads(json_match.group(0))
    except Exception as e:
        logger.warning(f"[KnowledgeExtraction] Groq extraction failed: {e}. Falling back to Gemini...")
        try:
            gemini = GeminiLLM()
            raw_text = gemini.chat(
                system_prompt=KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1
            )
            json_match = re.search(r"\{[\s\S]*\}", str(raw_text))
            if json_match:
                extracted_data = json.loads(json_match.group(0))
        except Exception as ge:
            logger.error(f"[KnowledgeExtraction] Both LLMs failed extraction: {ge}")
            return {"chunks_indexed": 0, "suggestions_found": 0, "error": str(ge)}

    # 2. Process extracted facts
    product_truths = extracted_data.get("product_truths", [])
    project_truths = extracted_data.get("project_truths", [])
    claims = extracted_data.get("claims", [])
    new_suggestions = extracted_data.get("new_entity_suggestions", [])

    chunks_to_embed: List[Dict[str, Any]] = []

    # Format Product Truths
    for pt in product_truths:
        fact = pt.get("fact", "").strip()
        if fact:
            chunks_to_embed.append({
                "content": fact,
                "metadata": {
                    "tag": "PRODUCT_TRUTH",
                    "entity": pt.get("entity", "Product"),
                    "type": pt.get("type", "specification"),
                    "source_doc": source_filename or "Uploaded Document"
                }
            })

    # Format Project Truths
    for pjt in project_truths:
        fact = pjt.get("fact", "").strip()
        if fact:
            chunks_to_embed.append({
                "content": fact,
                "metadata": {
                    "tag": "PROJECT_TRUTH",
                    "entity": pjt.get("entity", "Project"),
                    "type": pjt.get("type", "project_detail"),
                    "source_doc": source_filename or "Uploaded Document"
                }
            })

    # Format Claims
    for clm in claims:
        fact = clm.get("claim", "").strip()
        if fact:
            chunks_to_embed.append({
                "content": fact,
                "metadata": {
                    "tag": "INDUSTRY_CLAIM",
                    "source_detail": clm.get("source_detail", ""),
                    "source_doc": source_filename or "Uploaded Document"
                }
            })

    # 3. Embed & Insert Chunks into Supabase
    indexed_count = 0
    if chunks_to_embed:
        embedder = EmbeddingProvider()
        texts = [c["content"] for c in chunks_to_embed]
        try:
            embeddings = embedder.embed_batch(texts)
            supa = get_supabase_client()
            for chunk_item, emb in zip(chunks_to_embed, embeddings):
                if not emb:
                    continue
                row = {
                    "document_id": document_id,
                    "content": chunk_item["content"],
                    "metadata": chunk_item["metadata"],
                    "embedding": emb
                }
                if supa:
                    try:
                        supa.table("knowledge_chunks").insert(row).execute()
                        indexed_count += 1
                    except Exception as ie:
                        logger.warning(f"Error inserting chunk: {ie}")
                else:
                    indexed_count += 1
        except Exception as emb_err:
            logger.error(f"[KnowledgeExtraction] Embedding generation failed: {emb_err}")

    # 4. Handle Pending Entity Suggestions
    registered_suggestions = 0
    for sugg in new_suggestions:
        s_type = sugg.get("type", "product").lower()
        s_name = sugg.get("name", "").strip()
        s_context = sugg.get("context", "").strip()
        if s_name:
            # Check against known entities
            is_known = False
            if s_type == "product" and any(s_name.lower() == p.lower() for p in known_products):
                is_known = True
            elif s_type == "project" and any(s_name.lower() == p.lower() for p in known_projects):
                is_known = True

            if not is_known:
                add_pending_suggestion(
                    entity_type=s_type,
                    name=s_name,
                    context=s_context,
                    source_doc=source_filename or "Uploaded Document"
                )
                registered_suggestions += 1

    logger.info(
        f"[KnowledgeExtraction] Extracted {indexed_count} atomic fact chunks, "
        f"{registered_suggestions} new entity suggestions from '{source_filename}'."
    )

    return {
        "chunks_indexed": indexed_count,
        "suggestions_found": registered_suggestions,
        "product_truths": len(product_truths),
        "project_truths": len(project_truths),
        "claims": len(claims)
    }
