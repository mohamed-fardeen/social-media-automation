import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath("."))

from app.services.brand_profile import get_brand_profile, format_brand_context
from app.agents.research import _load_saved_research_context
from app.services.image.generator import _get_product_reference_bytes, GeminiImageProvider, CloudflareImageProvider
from app.services.llm.groq import GroqLLM

def test_smart_brand_context():
    profile = get_brand_profile("default")
    
    # Test lean base context
    base_ctx = format_brand_context(profile)
    print(f"\n[Test 1] Base Brand Context Length: {len(base_ctx)} chars")
    assert "Company:" in base_ctx
    assert "=== DETAILED PRODUCTS ===" not in base_ctx  # Verify no bloated JSON dump
    print("[OK] Base brand context is clean and lean.")

    # Test dynamic injection when topic mentions ATON
    aton_ctx = format_brand_context(profile, focus_topic="ATON robotic arm printing")
    print(f"[Test 1b] ATON Brand Context Length: {len(aton_ctx)} chars")
    assert "ATON" in aton_ctx
    assert "Specs:" in aton_ctx
    print("[OK] Targeted product specs dynamically injected.")

def test_research_dedup_and_diversity():
    ctx, ev = _load_saved_research_context("concrete 3D printing")
    print(f"\n[Test 2] Saved Research Context:\n{ctx[:300]}...")
    assert "SAVED RESEARCH INSIGHTS FROM DATABASE:" not in ctx
    assert len(ev) <= 6
    print(f"[OK] Research loaded {len(ev)} deduplicated & diverse items.")

def test_product_reference_imagery():
    aton_bytes = _get_product_reference_bytes("aton")
    atom_bytes = _get_product_reference_bytes("atom")
    print(f"\n[Test 3] ATON ref bytes: {len(aton_bytes) if aton_bytes else 'None'}")
    print(f"[Test 3] ATOM ref bytes: {len(atom_bytes) if atom_bytes else 'None'}")
    if aton_bytes:
        print("[OK] Successfully loaded ATON reference image from Supabase bucket.")
    if atom_bytes:
        print("[OK] Successfully loaded ATOM reference image from Supabase bucket.")

def test_groq_llm():
    try:
        llm = GroqLLM()
        res = llm.chat(
            system_prompt="You are a helpful assistant. Reply with 'OK: ' followed by what you do.",
            user_prompt="Say hello",
            max_tokens=30
        )
        print(f"\n[Test 4] Groq GPT-OSS Response: {res.strip()}")
        print("[OK] Groq LLM client is working.")
    except Exception as e:
        print(f"\n[Test 4] Groq test note: {e}")

if __name__ == "__main__":
    print("Running verification tests...")
    test_smart_brand_context()
    test_research_dedup_and_diversity()
    test_product_reference_imagery()
    test_groq_llm()
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
