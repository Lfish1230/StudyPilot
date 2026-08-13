import { useState, type FormEvent, type KeyboardEvent } from "react";

interface ChatComposerProps {
  draft: string;
  isSending: boolean;
  onDraftChange(value: string): void;
  onSend(): void;
}

export function ChatComposer({
  draft,
  isSending,
  onDraftChange,
  onSend,
}: ChatComposerProps) {
  const [isComposing, setIsComposing] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.trim() && !isSending) onSend();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !isComposing) {
      event.preventDefault();
      if (draft.trim() && !isSending) onSend();
    }
  }

  return (
    <form className="chat-composer" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="chat-question">向课程资料提问</label>
      <textarea
        id="chat-question"
        maxLength={2000}
        onChange={(event) => onDraftChange(event.target.value)}
        onCompositionEnd={() => setIsComposing(false)}
        onCompositionStart={() => setIsComposing(true)}
        onKeyDown={handleKeyDown}
        placeholder="例如：请结合资料解释 TCP 为什么需要三次握手"
        rows={3}
        value={draft}
      />
      <div>
        <span>{draft.length}/2000 · Enter 发送，Shift + Enter 换行</span>
        <button className="primary-button" disabled={!draft.trim() || isSending} type="submit">
          {isSending ? "回答中…" : "发送问题"}
        </button>
      </div>
    </form>
  );
}
