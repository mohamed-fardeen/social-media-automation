"use client";

import { useCallback, useState, useRef } from "react";
import { useDocuments, getStore } from "@/lib/store";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { StatusDot } from "@/components/ui/StatusDot";
import { Chip } from "@/components/ui/Chip";
import { getSupabase } from "@/lib/supabase";
import { n8n } from "@/lib/n8n";
import { formatBytes, formatRelative, formatNumber } from "@/lib/utils";
import { Upload, FileText, File, Image as ImageIcon, FileArchive, Search, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import type { Document } from "@/lib/types";

export default function KnowledgePage() {
  const documents = useDocuments();
  const [active, setActive] = useState<Document | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [filter, setFilter] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const filtered = documents.filter((d) =>
    d.name.toLowerCase().includes(filter.toLowerCase()),
  );

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    const arr = Array.from(files);
    for (const file of arr) {
      const id = `doc_${crypto.randomUUID()}`;
      const doc: Document = {
        id,
        name: file.name,
        size_bytes: file.size,
        mime_type: file.type || "application/octet-stream",
        status: "uploading",
        uploaded_at: new Date().toISOString(),
        storage_path: `${id}/${file.name}`,
        chunks: 0,
        pages: 0,
      };
      getStore().addDocument(doc);

      // Try real Supabase upload, otherwise simulate
      const supa = getSupabase();
      if (supa) {
        const { error } = await supa.storage.from("knowledge").upload(doc.storage_path, file);
        if (error) {
          getStore().updateDocument(id, { status: "failed", error: error.message });
          continue;
        }
      } else {
        await new Promise((r) => setTimeout(r, 700));
      }
      // Move to processing
      getStore().updateDocument(id, { status: "processing" });
      // Fire webhook
      n8n.ingest({
        source: "document",
        filename: file.name,
        storage_path: doc.storage_path,
        brand_id: "brand_atlas",
      });
      await new Promise((r) => setTimeout(r, 1400));
      getStore().updateDocument(id, { status: "indexing" });
      await new Promise((r) => setTimeout(r, 1200));
      const chunks = Math.max(1, Math.round(file.size / 6000));
      getStore().updateDocument(id, { status: "indexed", chunks, pages: Math.max(1, Math.round(chunks / 6)) });
    }
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Knowledge"
        title="The brand's memory."
        description="Drop brand voice documents, audience research, and competitor teardowns. The RAG agent reads them before every generation."
        actions={
          <Button
            variant="primary"
            iconLeft={<Upload className="h-4 w-4" />}
            onClick={() => fileInput.current?.click()}
          >
            Upload documents
          </Button>
        }
      />

      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.zip"
        onChange={(e) => e.target.files && handleFiles(e.target.files)}
      />

      {/* Dropzone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "relative rounded-xl border border-dashed transition-colors p-10 grid place-items-center text-center",
          dragOver
            ? "dropzone-active border-sodium-500"
            : "border-ink-600 bg-ink-900/30",
        )}
      >
        <div className="grid h-12 w-12 place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-100">
          <Upload className="h-5 w-5" />
        </div>
        <h3 className="mt-4 text-base font-medium text-ink-50">Drop files to index</h3>
        <p className="mt-1 max-w-md text-sm text-ink-200">
          PDF, DOCX, TXT, MD, images, or ZIP. We parse, chunk, embed, and ship to the Knowledge/RAG agent.
        </p>
        <div className="mt-4 flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
            Browse files
          </Button>
          <span className="font-mono text-2xs text-ink-300">or drop anywhere</span>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-3">
        <label className="flex-1 flex items-center gap-2 rounded-md border border-ink-600 bg-ink-900 px-3 h-9 text-sm text-ink-300 focus-within:border-ink-500">
          <Search className="h-4 w-4 text-ink-300" />
          <input
            placeholder="Filter documents…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="flex-1 bg-transparent outline-none text-ink-50 placeholder:text-ink-300"
          />
        </label>
        <div className="font-mono text-2xs text-ink-300">
          {documents.length} documents · {formatNumber(documents.reduce((s, d) => s + d.chunks, 0))} chunks
        </div>
      </div>

      {/* Document grid + detail */}
      <div className="grid grid-cols-12 gap-6">
        <ul className="col-span-12 lg:col-span-7 grid grid-cols-1 gap-px bg-ink-600 rounded-lg overflow-hidden border border-ink-600">
          {filtered.map((d) => (
            <li key={d.id} className="bg-ink-900">
              <button
                onClick={() => setActive(d)}
                className={cn(
                  "w-full grid grid-cols-12 gap-4 items-center px-4 py-3.5 text-left transition-colors",
                  active?.id === d.id ? "bg-ink-850" : "hover:bg-ink-850/50",
                )}
              >
                <div className="col-span-5 flex items-center gap-3 min-w-0">
                  <DocIcon mime={d.mime_type} />
                  <div className="min-w-0">
                    <div className="text-sm text-ink-50 truncate">{d.name}</div>
                    <div className="mt-0.5 font-mono text-2xs text-ink-300">{formatBytes(d.size_bytes)}</div>
                  </div>
                </div>
                <div className="col-span-2 font-mono text-2xs text-ink-300">{d.chunks} chunks</div>
                <div className="col-span-2 font-mono text-2xs text-ink-300">{d.pages > 0 ? `${d.pages} pages` : "—"}</div>
                <div className="col-span-2">
                  <StatusDot
                    status={
                      d.status === "indexed"
                        ? "indexed"
                        : d.status === "indexing"
                          ? "indexing"
                          : d.status === "processing"
                            ? "processing"
                            : d.status === "uploading"
                              ? "uploading"
                              : "failed"
                    }
                    withLabel
                  />
                </div>
                <div className="col-span-1 text-right font-mono text-2xs text-ink-300">{formatRelative(d.uploaded_at)}</div>
              </button>
            </li>
          ))}
        </ul>

        <aside className="col-span-12 lg:col-span-5 rounded-xl border border-ink-600 bg-ink-900 overflow-hidden">
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
                      <div className="text-base font-medium text-ink-50 truncate">{active.name}</div>
                      <div className="font-mono text-2xs text-ink-300 mt-0.5">{active.storage_path}</div>
                    </div>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-px bg-ink-600 rounded-lg overflow-hidden border border-ink-600">
                    <Detail label="Size" value={formatBytes(active.size_bytes)} />
                    <Detail label="Pages" value={active.pages > 0 ? active.pages.toString() : "—"} />
                    <Detail label="Chunks" value={active.chunks.toString()} />
                    <Detail label="Embedding" value="1536-d" />
                    <Detail label="Uploaded" value={formatRelative(active.uploaded_at)} />
                    <Detail label="Status" value={active.status} />
                  </div>
                </div>
                <div className="p-5">
                  <div className="mono-label mb-3">Indexing log</div>
                  <ol className="space-y-2 font-mono text-xs">
                    <Log done label="Uploaded" detail={`${formatBytes(active.size_bytes)} → ${active.storage_path}`} />
                    <Log done={active.status !== "uploading"} label="Parsed" detail={`${active.pages} pages detected`} />
                    <Log done={active.status === "indexed" || active.status === "indexing"} label="Chunked" detail={`${active.chunks} chunks, 800 token avg`} />
                    <Log done={active.status === "indexed"} label="Embedded" detail="text-embedding-3-large" />
                    <Log done={active.status === "indexed"} label="Indexed" detail="knowledge_chunks table" />
                  </ol>
                </div>
                <div className="p-5 flex items-center gap-2">
                  <Button variant="outline" size="sm">Re-index</Button>
                  <Button variant="danger" size="sm" iconLeft={<Trash2 className="h-3.5 w-3.5" />}>Remove</Button>
                </div>
              </motion.div>
            ) : (
              <motion.div key="empty" className="h-full grid place-items-center text-center px-6 py-16">
                <div>
                  <span className="grid h-10 w-10 mx-auto place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-200">
                    <FileText className="h-4 w-4" />
                  </span>
                  <h3 className="mt-4 text-base font-medium text-ink-50">Select a document</h3>
                  <p className="mt-1 max-w-sm text-sm text-ink-200">
                    See chunks, embeddings, and the parsing log for each document.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </aside>
      </div>
    </div>
  );
}

function DocIcon({ mime, large }: { mime: string; large?: boolean }) {
  const size = large ? "h-10 w-10" : "h-8 w-8";
  const iconSize = large ? "h-4 w-4" : "h-3.5 w-3.5";
  if (mime.includes("pdf")) return <span className={`grid ${size} place-items-center rounded-md border border-ink-600 bg-ink-850 text-sodium-500`}><FileText className={iconSize} /></span>;
  if (mime.includes("image")) return <span className={`grid ${size} place-items-center rounded-md border border-ink-600 bg-ink-850 text-steel-500`}><ImageIcon className={iconSize} /></span>;
  if (mime.includes("zip")) return <span className={`grid ${size} place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-100`}><FileArchive className={iconSize} /></span>;
  if (mime.includes("word") || mime.includes("doc")) return <span className={`grid ${size} place-items-center rounded-md border border-ink-600 bg-ink-850 text-steel-400`}><FileText className={iconSize} /></span>;
  return <span className={`grid ${size} place-items-center rounded-md border border-ink-600 bg-ink-850 text-ink-100`}><File className={iconSize} /></span>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ink-900 px-3.5 py-3">
      <div className="font-mono text-2xs uppercase tracking-wider text-ink-300">{label}</div>
      <div className="mt-1 text-sm text-ink-50 font-mono nums truncate">{value}</div>
    </div>
  );
}

function Log({ done, label, detail }: { done: boolean; label: string; detail: string }) {
  return (
    <li className="flex items-start gap-2">
      <span className={`mt-1 h-1.5 w-1.5 rounded-full ${done ? "bg-live-ok" : "bg-ink-500"}`} />
      <div>
        <div className={done ? "text-ink-100" : "text-ink-300"}>{label}</div>
        <div className="text-ink-300 text-2xs">{detail}</div>
      </div>
    </li>
  );
}
