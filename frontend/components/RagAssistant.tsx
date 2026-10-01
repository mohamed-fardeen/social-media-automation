"use client";

import { FormEvent, useRef, useState } from "react";
import { Bot, Loader2, MessageCircle, Send, X } from "lucide-react";
import { api, type RagCitation } from "@/lib/api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: RagCitation[];
};

export function RagAssistant() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Ask me about indexed documents. I will answer from retrieved chunks and cite pages when available.",
    },
  ]);
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setQuestion("");
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);

    const result = await api.ragChat(trimmed);
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        content: result?.answer || "I could not reach the RAG service. Check the backend and indexed documents.",
        citations: result?.citations || [],
      },
    ]);
    setLoading(false);
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {open && (
        <section className="w-[min(calc(100vw-2.5rem),560px)] overflow-hidden rounded-lg border border-[#2e3038] bg-[#111216]/95 shadow-2xl backdrop-blur">
          <header className="flex h-14 items-center justify-between border-b border-[#23252b] px-5">
            <div className="flex items-center gap-2 text-sm font-medium text-[#f4f4f5]">
              <Bot className="h-4 w-4 text-[#f5b947]" />
              Document assistant
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="grid h-8 w-8 place-items-center rounded-md text-[#8b8e98] transition hover:bg-[#1d1f25] hover:text-white"
              aria-label="Close document assistant"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          <div className="max-h-[min(62vh,620px)] min-h-[360px] space-y-3 overflow-y-auto px-5 py-5">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={message.role === "user" ? "ml-8 text-right" : "mr-8 text-left"}
              >
                <div
                  className={
                    message.role === "user"
                      ? "inline-block rounded-lg bg-[#f5b947] px-3 py-2 text-sm text-[#15110a]"
                      : "inline-block rounded-lg border border-[#23252b] bg-[#17191f] px-3 py-2 text-sm text-[#edeef0]"
                  }
                >
                  <p className="whitespace-pre-wrap leading-6">{message.content}</p>
                  {message.citations && message.citations.length > 0 && (
                    <div className="mt-3 space-y-1 border-t border-[#2e3038] pt-2 text-xs text-[#a8abb4]">
                      {message.citations.slice(0, 4).map((citation) => (
                        <div key={`${citation.source}-${citation.page}-${citation.index}`}>
                          [{citation.index}] {citation.source}
                          {citation.page ? `, page ${citation.page}` : ""}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="mr-8 inline-flex items-center gap-2 rounded-lg border border-[#23252b] bg-[#17191f] px-3 py-2 text-sm text-[#a8abb4]">
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching documents
              </div>
            )}
          </div>

          <form onSubmit={submit} className="flex gap-2 border-t border-[#23252b] p-4">
            <input
              ref={inputRef}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              className="h-11 min-w-0 flex-1 rounded-md border border-[#2e3038] bg-[#0b0c0f] px-3 text-sm text-white outline-none placeholder:text-[#5f636d] focus:border-[#f5b947]"
              placeholder="Ask about a document..."
            />
            <button
              type="submit"
              disabled={!question.trim() || loading}
              className="grid h-11 w-11 place-items-center rounded-md bg-[#f5b947] text-[#15110a] transition hover:bg-[#ffd06a] disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Send question"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => {
          setOpen((value) => !value);
          window.setTimeout(() => inputRef.current?.focus(), 60);
        }}
        className="grid h-12 w-12 place-items-center rounded-full border border-[#3a3323] bg-[#f5b947] text-[#15110a] shadow-xl transition hover:bg-[#ffd06a]"
        aria-label="Open document assistant"
      >
        <MessageCircle className="h-5 w-5" />
      </button>
    </div>
  );
}
