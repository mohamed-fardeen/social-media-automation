"use client";

import { useBrand } from "@/lib/store";
import { PlatformIcon } from "@/components/ui/PlatformIcon";
import { formatNumber, formatRelative } from "@/lib/utils";
import { Heart, MessageCircle, Send, Bookmark, MoreHorizontal } from "lucide-react";
import type { PostDraft } from "@/lib/types";

export function InstagramPreview({ draft }: { draft: PostDraft }) {
  const brand = useBrand();

  return (
    <div className="rounded-xl border border-ink-600 bg-black overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-[#FEDA75] via-[#FA7E1E] to-[#D62976] text-[10px] font-semibold text-white">
            {brand.name[0]}
          </span>
          <div className="leading-tight">
            <div className="text-[13px] font-semibold text-white">{brand.ig_handle}</div>
            <div className="text-[11px] text-white/60">Sponsored</div>
          </div>
        </div>
        <MoreHorizontal className="h-4 w-4 text-white/80" />
      </div>

      {/* Image */}
      <div className="aspect-square w-full bg-ink-800 relative">
        {draft.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={draft.image_url}
            alt=""
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="grid h-full w-full place-items-center text-ink-300 text-xs">
            image
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between px-3.5 py-2.5 text-white">
        <div className="flex items-center gap-4">
          <Heart className="h-5 w-5" />
          <MessageCircle className="h-5 w-5" />
          <Send className="h-5 w-5" />
        </div>
        <Bookmark className="h-5 w-5" />
      </div>

      {/* Caption */}
      <div className="px-3.5 pb-3.5 text-[13px] text-white">
        <span className="font-semibold">{brand.ig_handle}</span>{" "}
        <span className="whitespace-pre-line">{draft.caption}</span>
        {draft.hashtags.length > 0 && (
          <div className="mt-1.5 text-[#E0F1FF]">{draft.hashtags.join(" ")}</div>
        )}
        <div className="mt-2 text-[11px] uppercase tracking-wider text-white/40">
          {formatRelative(new Date())}
        </div>
      </div>
    </div>
  );
}
