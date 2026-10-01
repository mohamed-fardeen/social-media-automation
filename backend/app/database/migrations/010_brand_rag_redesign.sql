-- Migration 010: Brand Profile Redesign + Reference Images + Entity Suggestions
-- Supporting flat Brand Profile architecture and bounded fact extraction.

-- 1. Brand Reference Images Table
CREATE TABLE IF NOT EXISTS public.brand_reference_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_url TEXT NOT NULL,
    linked_to_type TEXT NOT NULL CHECK (linked_to_type IN ('product', 'project')),
    linked_to_name TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brand_ref_images_name ON public.brand_reference_images(linked_to_name);

-- 2. Pending Entity Suggestions Table (Extracted by Document Ingest Agent)
CREATE TABLE IF NOT EXISTS public.pending_entity_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('product', 'project')),
    name TEXT NOT NULL,
    context TEXT NOT NULL,
    source_doc TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'ignored')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_entity_status ON public.pending_entity_suggestions(status);

-- 3. Initial Seed for Reference Images (Only verified available product images)
INSERT INTO public.brand_reference_images (image_url, linked_to_type, linked_to_name)
VALUES
    ('https://kdnbwgeofduhkmvbyuul.supabase.co/storage/v1/object/public/brand-assets/products/Atom%20V1.jpeg', 'product', 'ATOM'),
    ('https://kdnbwgeofduhkmvbyuul.supabase.co/storage/v1/object/public/brand-assets/products/Atom_V2.jpeg', 'product', 'ATOM'),
    ('https://kdnbwgeofduhkmvbyuul.supabase.co/storage/v1/object/public/brand-assets/products/Aton.jpeg', 'product', 'ATON')
ON CONFLICT DO NOTHING;
