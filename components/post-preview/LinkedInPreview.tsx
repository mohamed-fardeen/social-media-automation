"use client";

import { useBrand } from "@/lib/store";
import { formatNumber } from "@/lib/utils";
import { ThumbsUp, MessageSquare, Repeat2, Send, MoreHorizontal } from "lucide-react";
import type { PostDraft } from "@/lib/types";

export function LinkedInPreview({ draft }: { draft: PostDraft }) {
  const brand = useBrand();

  return (
    <div className="rounded-xl border border-ink-600 bg-[#1B1F23] overflow-hidden text-white">
      {/* Header */}
      <div className="flex items-start gap-3 px-4 pt-4">
        <span className="grid h-12 w-12 place-items-center rounded-full bg-ink-700 text-sm font-semibold text-white">
          {brand.name[0]}
        </span>
        <div className="flex-1 leading-tight">
          <div className="text-sm font-semibold">{brand.name}</div>
          <div className="text-xs text-white/60">{(brand as any).li_handle ? `@${brand.ig_handle}` : brand.name}</div>
          <div className="text-xs text-white/60">2h • 🌐</div>
        </div>
        <MoreHorizontal className="h-4 w-4 text-white/60" />
      </div>

      {/* Caption */}
      <div className="px-4 py-3 text-[13px] leading-relaxed whitespace-pre-line">
        {draft.caption}
      </div>

      {/* Image */}
      {draft.image_url && (
        <div className="border-y border-white/10">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={draft.image_url} alt="" className="w-full" />
        </div>
      )}

      {/* Social counts */}
      <div className="flex items-center justify-between px-4 py-2.5 text-xs text-white/60">
        <div className="flex items-center gap-1">
          <span className="grid h-4 w-4 place-items-center rounded-full bg-[#0A66C2] text-[8px]">👍</span>
          <span>{formatNumber(482)}</span>
        </div>
        <div className="flex gap-3">
          <span>{formatNumber(38)} comments</span>
          <span>{formatNumber(12)} reposts</span>
        </div>
      </div>

      <div className="hairline" />

      {/* Actions */}
      <div className="flex items-center justify-around px-2 py-1.5 text-xs text-white/70">
        <button className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md hover:bg-white/5">
          <ThumbsUp className="h-4 w-4" /> Like
        </button>
        <button className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md hover:bg-white/5">
          <MessageSquare className="h-4 w-4" /> Comment
        </button>
        <button className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md hover:bg-white/5">
          <Repeat2 className="h-4 w-4" /> Repost
        </button>
        <button className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md hover:bg-white/5">
          <Send className="h-4 w-4" /> Send
        </button>
      </div>
    </div>
  );
}
