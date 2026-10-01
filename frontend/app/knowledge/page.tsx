"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  File,
  FileArchive,
  FileText,
  Image as ImageIcon,
  Search,
  Trash2,
  Upload,
  Sparkles,
  Check,
  X,
  Plus,
  Layers,
  Camera
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { StatusDot } from "@/components/ui/StatusDot";
import { api, type EntitySuggestion, type ReferenceImage } from "@/lib/api";
import { getStore, useDocuments } from "@/lib/store";
import type { Document } from "@/lib/types";
import { cn, formatBytes, formatNumber, formatRelative } from "@/lib/utils";

// Dynamically loaded from Brand Profile

export default function KnowledgePage() {
  const documents = useDocuments();
  const [active, setActive] = useState<Document | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [filter, setFilter] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  // Suggestions & Reference Images State
  const [suggestions, setSuggestions] = useState<EntitySuggestion[]>([]);
  const [refImages, setRefImages] = useState<ReferenceImage[]>([]);
  const [showRefUploadModal, setShowRefUploadModal] = useState(false);
  const [refSelectedEntity, setRefSelectedEntity] = useState("");
  const [refEntityType, setRefEntityType] = useState("product");
  const [refCustomName, setRefCustomName] = useState("");
  const [refUploading, setRefUploading] = useState(false);
  const [entityOptions, setEntityOptions] = useState<{name: string, type: string}[]>([]);
  const refFileInput = useRef<HTMLInputElement>(null);

  const refreshDocuments = useCallback(async () => {
    const docs = await api.listDocuments();
    getStore().patch({ documents: docs as Document[] });
  }, []);

  const refreshSuggestionsAndImages = useCallback(async () => {
    try {
      const [suggs, imgs, brand] = await Promise.all([
        api.listEntitySuggestions("pending"),
        api.listReferenceImages(),
        api.getBrandProfile()
      ]);
      setSuggestions(suggs || []);
      setRefImages(imgs || []);
      if (brand) {
        const opts: {name: string, type: string}[] = [];
        (brand.products || []).forEach(p => p.name && opts.push({ name: p.name, type: "product" }));
        (brand.projects || []).forEach(p => p.name && opts.push({ name: p.name, type: "project" }));
        setEntityOptions(opts);
        if (opts.length > 0 && !refSelectedEntity) {
          setRefSelectedEntity(opts[0].name);
          setRefEntityType(opts[0].type);
        }
      }
    } catch (e) {
      console.warn("Failed to load suggestions/images/brand", e);
    }
  }, [refSelectedEntity]);

  useEffect(() => {
    refreshDocuments();
    refreshSuggestionsAndImages();
  }, [refreshDocuments, refreshSuggestionsAndImages]);

  useEffect(() => {
    if (!active) return;
    const latest = documents.find((doc) => doc.id === active.id);
    if (latest && latest !== active) setActive(latest);
    if (!latest) setActive(null);
  }, [active, documents]);

  const filtered = documents.filter((document) =>
    getDocumentName(document).toLowerCase().includes(filter.toLowerCase()),
  );

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const tempId = `doc_upload_${crypto.randomUUID()}`;
      const optimisticDoc: Document = {
        id: tempId,
        file_name: file.name,
        mime_type: file.type || "application/octet-stream",
        status: "uploading",
        created_at: new Date().toISOString(),
        storage_path: "",
        chunks: 0,
        pages: 0,
      };
      getStore().addDocument(optimisticDoc);

      const result = await api.uploadDocument(file);
      if (!result) {
        getStore().updateDocument(tempId, { status: "failed", error: "Upload to backend failed" });
        continue;
      }

      const realId = result.document_id;
      getStore().updateDocument(tempId, {
        id: realId,
        file_name: result.name,
        status: "processing",
        storage_path: result.storage_path,
      });

      for (let attempt = 0; attempt < 90; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const indexedDoc = await api.getDocument(realId);
        if (!indexedDoc) continue;
        getStore().updateDocument(realId, indexedDoc as Partial<Document>);
        if (indexedDoc.status === "indexed" || indexedDoc.status === "failed") break;
      }
    }

    refreshDocuments();
    refreshSuggestionsAndImages();
  }, [refreshDocuments, refreshSuggestionsAndImages]);

  const removeDocument = useCallback(async (document: Document) => {
    const ok = await api.deleteDocument(document.id);
    if (!ok) {
      getStore().updateDocument(document.id, { error: "Remove failed. Check backend logs." });
      return;
    }
    getStore().removeDocument(document.id);
    if (active?.id === document.id) setActive(null);
  }, [active?.id]);

  const handleApproveSuggestion = async (id: string) => {
    const ok = await api.approveEntitySuggestion(id);
    if (ok) {
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    }
  };

  const handleIgnoreSuggestion = async (id: string) => {
    const ok = await api.ignoreEntitySuggestion(id);
    if (ok) {
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    }
  };

  const handleUploadRefImage = async (file: File) => {
    setRefUploading(true);
    const targetName = refSelectedEntity === "custom" ? refCustomName.trim() : refSelectedEntity;
    if (!targetName) {
      setRefUploading(false);
      return;
    }
    const res = await api.uploadReferenceImage(file, refEntityType, targetName);
    setRefUploading(false);
    if (res) {
      setShowRefUploadModal(false);
      refreshSuggestionsAndImages();
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Knowledge & RAG"
        title="Verified Knowledge Base"
        description="Atomic fact retrieval, bounded document knowledge extraction, and ground-truth reference imagery for 3DCP robotics."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              iconLeft={<Camera className="h-4 w-4" />}
              onClick={() => setShowRefUploadModal(true)}
            >
              Add Reference Image
            </Button>
            <Button
              variant="primary"
              iconLeft={<Upload className="h-4 w-4" />}
              onClick={() => fileInput.current?.click()}
            >
              Upload Document
            </Button>
          </div>
        }
      />

      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.zip"
        onChange={(event) => event.target.files && handleFiles(event.target.files)}
      />

      {/* ── Pending Entity Suggestions Banner ── */}
      {suggestions.length > 0 && (
        <div className="rounded-xl border border-sodium-500/40 bg-sodium-500/10 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sodium-400 font-medium text-sm">
              <Sparkles className="h-4 w-4" />
              <span>Pending Entity Suggestions ({suggestions.length})</span>
            </div>
            <span className="text-xs text-ink-300">
              Found in uploaded docs. Human approval required to add to Brand Profile.
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            {suggestions.map((sug) => (
              <div
                key={sug.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-ink-700 bg-ink-900/80 p-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase",
                        sug.type === "product"
                          ? "bg-steel-500/20 text-steel-400 border border-steel-500/30"
                          : "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                      )}
                    >
                      {sug.type}
                    </span>
                    <span className="font-semibold text-ink-100 text-sm">{sug.name}</span>
                  </div>
                  <p className="text-xs text-ink-300 line-clamp-2 leading-relaxed">{sug.context}</p>
                  <p className="text-[11px] font-mono text-ink-400">Source: {sug.source_doc}</p>
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  <button
                    onClick={() => handleApproveSuggestion(sug.id)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-sodium-500/20 hover:bg-sodium-500/30 text-sodium-300 text-xs font-medium transition"
                    title="Add to Brand Profile"
                  >
                    <Check className="h-3 w-3" /> Approve
                  </button>
                  <button
                    onClick={() => handleIgnoreSuggestion(sug.id)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-ink-800 hover:bg-ink-700 text-ink-400 hover:text-ink-200 text-xs transition"
                    title="Dismiss"
                  >
                    <X className="h-3 w-3" /> Ignore
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Reference Images Gallery ── */}
      <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-sodium-400" />
            <h3 className="text-sm font-semibold text-ink-100">Brand Reference Images ({refImages.length})</h3>
          </div>
          <span className="text-xs text-ink-400">
            Ground-truth visual references for exact machine & project image grounding.
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {refImages.map((img) => (
            <div
              key={img.id}
              className="group relative overflow-hidden rounded-lg border border-ink-700 bg-ink-950 flex flex-col"
            >
              <div className="aspect-video w-full overflow-hidden bg-ink-900">
                <img
                  src={img.image_url}
                  alt={img.linked_to_name}
                  className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
                  onError={(e) => {
                    // Fallback icon placeholder if external image URL is blocked
                    e.currentTarget.style.display = "none";
                  }}
                />
              </div>
              <div className="p-2 bg-ink-900/90 border-t border-ink-800">
                <div className="text-xs font-medium text-ink-100 truncate">{img.linked_to_name}</div>
                <div className="text-[10px] font-mono text-ink-400 uppercase">{img.linked_to_type}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Document Upload Drag-and-Drop ── */}
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          if (event.dataTransfer.files.length) handleFiles(event.dataTransfer.files);
        }}
        className={cn(
          "relative grid place-items-center rounded-xl border border-dashed p-10 text-center transition-colors",
          dragOver ? "dropzone-active border-sodium-500" : "border-ink-600 bg-ink-900/30",
        )}
      >
        <div className="grid h-12 w-12 place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-100">
          <Upload className="h-5 w-5" />
        </div>
        <h3 className="mt-4 text-base font-medium text-ink-50">Drop files to index</h3>
        <p className="mt-1 max-w-md text-sm text-ink-200">
          PDF, DOCX, TXT, MD, images, or ZIP. Extracts atomic facts, generates 384-d embeddings, and indexes into pgvector.
        </p>
        <div className="mt-4 flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
            Browse files
          </Button>
          <span className="font-mono text-2xs text-ink-300">or drop anywhere</span>
        </div>
      </div>

      {/* ── Documents Table & Detail ── */}
      <div className="flex items-center gap-3">
        <label className="flex h-9 flex-1 items-center gap-2 rounded-md border border-ink-600 bg-ink-900 px-3 text-sm text-ink-300 focus-within:border-ink-500">
          <Search className="h-4 w-4 text-ink-300" />
          <input
            placeholder="Filter documents..."
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="flex-1 bg-transparent text-ink-50 outline-none placeholder:text-ink-300"
          />
        </label>
        <div className="font-mono text-2xs text-ink-300">
          {documents.length} documents · {formatNumber(documents.reduce((sum, doc) => sum + (doc.chunks ?? 0), 0))} chunks
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <ul className="col-span-12 grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-ink-600 bg-ink-600 lg:col-span-7">
          {filtered.map((document) => (
            <li key={document.id} className="bg-ink-900">
              <button
                onClick={() => setActive(document)}
                className={cn(
                  "grid w-full grid-cols-12 items-center gap-4 px-4 py-3.5 text-left transition-colors",
                  active?.id === document.id ? "bg-ink-850" : "hover:bg-ink-850/50",
                )}
              >
                <div className="col-span-5 flex min-w-0 items-center gap-3">
                  <DocIcon mime={document.mime_type} />
                  <div className="min-w-0">
                    <div className="truncate text-sm text-ink-50">{getDocumentName(document)}</div>
                    <div className="mt-0.5 font-mono text-2xs text-ink-300">{formatBytes(getDocumentSize(document))}</div>
                  </div>
                </div>
                <div className="col-span-2 font-mono text-2xs text-ink-300">{document.chunks ?? 0} chunks</div>
                <div className="col-span-2 font-mono text-2xs text-ink-300">
                  {(document.pages ?? 0) > 0 ? `${document.pages} pages` : "-"}
                </div>
                <div className="col-span-2">
                  <StatusDot status={document.status} withLabel />
                </div>
                <div className="col-span-1 text-right font-mono text-2xs text-ink-300">
                  {formatRelative(getDocumentDate(document))}
                </div>
              </button>
            </li>
          ))}
        </ul>

        <aside className="col-span-12 overflow-hidden rounded-xl border border-ink-600 bg-ink-900 lg:col-span-5">
          <AnimatePresence mode="wait">
            {active ? (
              <motion.div
                key={active.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="divide-y divide-ink-600"
              >
                <div className="p-5">
                  <div className="flex items-center gap-3">
                    <DocIcon mime={active.mime_type} large />
                    <div className="min-w-0">
                      <div className="truncate text-base font-medium text-ink-50">{getDocumentName(active)}</div>
                      <div className="mt-0.5 font-mono text-2xs text-ink-300">{active.storage_path}</div>
                    </div>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-ink-600 bg-ink-600">
                    <Detail label="Size" value={formatBytes(getDocumentSize(active))} />
                    <Detail label="Pages" value={(active.pages ?? 0) > 0 ? String(active.pages) : "-"} />
                    <Detail label="Chunks" value={String(active.chunks ?? 0)} />
                    <Detail label="Embedding" value="384-d" />
                    <Detail label="Uploaded" value={formatRelative(getDocumentDate(active))} />
                    <Detail label="Status" value={active.status} />
                  </div>
                  {active.error && (
                    <div className="mt-4 rounded-md border border-red-500/30 bg-red-500/10 px-3.5 py-3">
                      <div className="font-mono text-2xs uppercase tracking-wider text-red-300">Error</div>
                      <p className="mt-1 text-sm leading-6 text-red-100">{active.error}</p>
                    </div>
                  )}
                </div>
                <div className="p-5">
                  <div className="mono-label mb-3">Indexing & Extraction Log</div>
                  <ol className="space-y-2 font-mono text-xs">
                    <Log done label="Uploaded" detail={`${formatBytes(getDocumentSize(active))} -> ${active.storage_path}`} />
                    <Log done={active.status !== "uploading"} label="Parsed & Extracted" detail={`${active.pages ?? 0} pages analyzed`} />
                    <Log done={active.status === "indexed" || active.status === "indexing"} label="Chunked & Fact Extracted" detail={`${active.chunks ?? 0} atomic chunks`} />
                    <Log done={active.status === "indexed"} label="Embedded" detail="gemini-embedding-001 (384-d)" />
                    <Log done={active.status === "indexed"} label="Indexed" detail="knowledge_chunks pgvector" />
                  </ol>
                </div>
                <div className="flex items-center gap-2 p-5">
                  <Button variant="outline" size="sm" onClick={refreshDocuments}>Refresh</Button>
                  <Button
                    variant="danger"
                    size="sm"
                    iconLeft={<Trash2 className="h-3.5 w-3.5" />}
                    onClick={() => removeDocument(active)}
                  >
                    Remove
                  </Button>
                </div>
              </motion.div>
            ) : (
              <motion.div key="empty" className="grid h-full place-items-center px-6 py-16 text-center">
                <div>
                  <span className="mx-auto grid h-10 w-10 place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-200">
                    <FileText className="h-4 w-4" />
                  </span>
                  <h3 className="mt-4 text-base font-medium text-ink-50">Select a document</h3>
                  <p className="mt-1 max-w-sm text-sm text-ink-200">
                    See atomic facts, embeddings, and parsing status for each document.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </aside>
      </div>

      {/* ── Reference Image Upload Modal ── */}
      {showRefUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-xl border border-ink-600 bg-ink-900 p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-ink-50">Add Brand Reference Image</h3>
              <button
                onClick={() => setShowRefUploadModal(false)}
                className="text-ink-400 hover:text-ink-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs text-ink-300">
              Link an authentic photograph or render to a specific product or project so image generation accurately grounds machine components.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-ink-300 block mb-1">This image shows:</label>
                <select
                  value={refSelectedEntity}
                  onChange={(e) => {
                    const val = e.target.value;
                    setRefSelectedEntity(val);
                    const match = entityOptions.find((o) => o.name === val);
                    if (match) setRefEntityType(match.type);
                  }}
                  className="w-full bg-ink-950 border border-ink-700 rounded-md p-2 text-sm text-ink-100 outline-none"
                >
                  {entityOptions.map((opt) => (
                    <option key={opt.name} value={opt.name}>
                      {opt.name} ({opt.type})
                    </option>
                  ))}
                  <option value="custom">Other / Custom Entity...</option>
                </select>
              </div>

              {refSelectedEntity === "custom" && (
                <div className="space-y-2">
                  <div>
                    <label className="text-xs font-medium text-ink-300 block mb-1">Entity Name</label>
                    <input
                      value={refCustomName}
                      onChange={(e) => setRefCustomName(e.target.value)}
                      placeholder="e.g. VORTEX Mixer"
                      className="w-full bg-ink-950 border border-ink-700 rounded-md p-2 text-sm text-ink-100 outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-ink-300 block mb-1">Type</label>
                    <select
                      value={refEntityType}
                      onChange={(e) => setRefEntityType(e.target.value)}
                      className="w-full bg-ink-950 border border-ink-700 rounded-md p-2 text-sm text-ink-100 outline-none"
                    >
                      <option value="product">Product</option>
                      <option value="project">Project</option>
                    </select>
                  </div>
                </div>
              )}

              <div>
                <label className="text-xs font-medium text-ink-300 block mb-1">Select Image File</label>
                <input
                  ref={refFileInput}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="w-full text-xs text-ink-300 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-ink-800 file:text-ink-200"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setShowRefUploadModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={refUploading}
                onClick={() => {
                  const file = refFileInput.current?.files?.[0];
                  if (file) handleUploadRefImage(file);
                }}
              >
                {refUploading ? "Uploading..." : "Save Reference Image"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DocIcon({ mime, large }: { mime: string; large?: boolean }) {
  const size = large ? "h-10 w-10" : "h-8 w-8";
  const iconSize = large ? "h-4 w-4" : "h-3.5 w-3.5";
  const className = `grid ${size} place-items-center rounded-md border border-ink-600 bg-ink-850`;
  if (mime.includes("pdf")) return <span className={`${className} text-sodium-500`}><FileText className={iconSize} /></span>;
  if (mime.includes("image")) return <span className={`${className} text-steel-500`}><ImageIcon className={iconSize} /></span>;
  if (mime.includes("zip")) return <span className={`${className} text-ink-100`}><FileArchive className={iconSize} /></span>;
  if (mime.includes("word") || mime.includes("doc")) return <span className={`${className} text-steel-400`}><FileText className={iconSize} /></span>;
  return <span className={`${className} text-ink-100`}><File className={iconSize} /></span>;
}

function getDocumentName(document: Document): string {
  const legacy = document as Document & { name?: string };
  return document.file_name || legacy.name || "Untitled document";
}

function getDocumentDate(document: Document): string | undefined {
  const legacy = document as Document & { uploaded_at?: string };
  return document.created_at || legacy.uploaded_at;
}

function getDocumentSize(document: Document): number | undefined {
  const legacy = document as Document & { size_bytes?: number };
  return legacy.size_bytes;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ink-900 px-3.5 py-3">
      <div className="font-mono text-2xs uppercase tracking-wider text-ink-300">{label}</div>
      <div className="nums mt-1 truncate font-mono text-sm text-ink-50">{value}</div>
    </div>
  );
}

function Log({ done, label, detail }: { done: boolean; label: string; detail: string }) {
  return (
    <li className="flex items-start gap-2">
      <span className={`mt-1 h-1.5 w-1.5 rounded-full ${done ? "bg-live-ok" : "bg-ink-500"}`} />
      <div>
        <div className={done ? "text-ink-100" : "text-ink-300"}>{label}</div>
        <div className="text-2xs text-ink-300">{detail}</div>
      </div>
    </li>
  );
}
