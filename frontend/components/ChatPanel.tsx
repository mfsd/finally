"use client";

import { FormEvent, useEffect, useRef } from "react";
import { Bot, Send, User } from "lucide-react";
import type { ChatMessage } from "@/lib/types";
import { Panel } from "./Panel";

export function ChatPanel({
  messages,
  busy,
  onSend
}: {
  messages: ChatMessage[];
  busy: boolean;
  onSend: (message: string) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const busyRef = useRef(busy);
  const onSendRef = useRef(onSend);

  useEffect(() => {
    busyRef.current = busy;
    onSendRef.current = onSend;
  }, [busy, onSend]);

  async function sendCurrent() {
    if (busyRef.current) return;
    const content = inputRef.current?.value.trim() ?? "";
    if (!content) return;
    if (inputRef.current) inputRef.current.value = "";
    await onSendRef.current(content);
  }

  useEffect(() => {
    const input = inputRef.current;
    const button = buttonRef.current;
    if (!input || !button) return;

    const handleClick = () => {
      void sendCurrent();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        void sendCurrent();
      }
    };

    button.addEventListener("click", handleClick);
    input.addEventListener("keydown", handleKeyDown);
    return () => {
      button.removeEventListener("click", handleClick);
      input.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    await sendCurrent();
  }

  return (
    <Panel title="AI Chat" testId="ai-chat" action={<span className="font-mono text-[11px] text-ally-yellow">FinAlly</span>}>
      <div className="grid h-[calc(100%-36px)] grid-rows-[minmax(0,1fr)_auto]">
        <div className="terminal-scrollbar space-y-3 overflow-auto p-3">
          {messages.map((item) => (
            <article key={item.id} className="grid grid-cols-[24px_1fr] gap-2">
              <div className="mt-0.5 flex h-6 w-6 items-center justify-center border border-terminal-border text-terminal-muted">
                {item.role === "assistant" ? <Bot size={14} /> : <User size={14} />}
              </div>
              <div>
                <p className="whitespace-pre-wrap text-sm leading-5 text-terminal-text">{item.content}</p>
                {item.actions && (
                  <div className="mt-2 space-y-1 font-mono text-[11px] text-terminal-muted">
                    {(item.actions.trades_executed ?? []).map((trade, index) => (
                      <div key={`trade-${index}`} className="text-ally-green" data-testid="chat-action">
                        EXEC {trade.side.toUpperCase()} {trade.quantity} {trade.ticker}
                      </div>
                    ))}
                    {(item.actions.trades_failed ?? []).map((trade, index) => (
                      <div key={`fail-${index}`} className="text-ally-red" data-testid="chat-action">
                        FAIL {trade.side.toUpperCase()} {trade.quantity} {trade.ticker}: {trade.error}
                      </div>
                    ))}
                    {(item.actions.watchlist_changes ?? []).map((action, index) => (
                      <div key={`watch-${index}`} className="text-ally-blue" data-testid="chat-action">
                        WATCHLIST {action.action.toUpperCase()} {action.ticker}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
          {busy && <div className="font-mono text-xs uppercase text-terminal-muted">Assistant thinking...</div>}
        </div>
        <form onSubmit={submit} className="flex gap-2 border-t border-terminal-border p-2" data-testid="chat-form">
          <input
            ref={inputRef}
            className="h-10 min-w-0 flex-1 border border-terminal-border bg-terminal-bg px-3 text-sm outline-none focus:border-ally-blue"
            placeholder="Ask FinAlly..."
            aria-label="Chat message"
            data-testid="chat-input"
          />
          <button
            ref={buttonRef}
            type="button"
            disabled={busy}
            className="flex h-10 w-10 items-center justify-center bg-ally-purple text-white disabled:opacity-50"
            aria-label="Send message"
            data-testid="chat-send-button"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </Panel>
  );
}
