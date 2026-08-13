import type { ReactNode } from "react";

import type { ConversationMessage, MessageCitation } from "../../api/contracts";

interface MessageListProps {
  messages: ConversationMessage[];
  optimisticQuestion: string;
  isLoading: boolean;
  isSending: boolean;
  onCitationClick(citation: MessageCitation): void;
}

function citedText(
  message: ConversationMessage,
  onCitationClick: (citation: MessageCitation) => void,
): ReactNode[] {
  const citations = new Map(message.citations.map((item) => [item.source_id.toUpperCase(), item]));
  return message.content.split(/(\[S\d+\])/gi).map((part, index) => {
    const match = part.match(/^\[(S\d+)\]$/i);
    const citation = match ? citations.get(match[1].toUpperCase()) : undefined;
    if (!citation) return <span key={`${index}-${part}`}>{part}</span>;
    const citationNumber = message.citations.indexOf(citation) + 1;
    return (
      <button
        aria-label={`查看引用 ${citationNumber}`}
        className="citation-token"
        key={`${citation.source_id}-${index}`}
        onClick={() => onCitationClick(citation)}
        type="button"
      >[{citationNumber}]</button>
    );
  });
}

export function MessageList({
  messages,
  optimisticQuestion,
  isLoading,
  isSending,
  onCitationClick,
}: MessageListProps) {
  if (isLoading) return <div className="chat-state" aria-live="polite">正在加载对话…</div>;
  if (messages.length === 0 && !optimisticQuestion) {
    return (
      <div className="chat-empty">
        <span aria-hidden="true">✨</span>
        <h1>从课程资料中寻找答案</h1>
        <p>我只会根据已处理完成的 PDF 回答，并为结论标注原文出处。</p>
      </div>
    );
  }
  return (
    <div className="message-list" aria-live="polite">
      {messages.map((message) => (
        <article className={`chat-message message-${message.role}`} key={message.id}>
          <div className="message-avatar" aria-hidden="true">{message.role === "user" ? "你" : "S"}</div>
          <div>
            <strong>{message.role === "user" ? "你" : "StudyPilot"}</strong>
            {message.refused && <span className="refusal-label">资料不足</span>}
            <p>{message.role === "assistant" ? citedText(message, onCitationClick) : message.content}</p>
          </div>
        </article>
      ))}
      {optimisticQuestion && (
        <article className="chat-message message-user pending-message">
          <div className="message-avatar" aria-hidden="true">你</div>
          <div><strong>你</strong><p>{optimisticQuestion}</p></div>
        </article>
      )}
      {isSending && (
        <div className="answer-loading" role="status">
          <span /><span /><span /> 正在检索资料并组织回答…
        </div>
      )}
    </div>
  );
}
