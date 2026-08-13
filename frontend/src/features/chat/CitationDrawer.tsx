import { useEffect } from "react";

import type { MessageCitation } from "../../api/contracts";

interface CitationDrawerProps {
  citation: MessageCitation | null;
  onClose(): void;
}

export function CitationDrawer({ citation, onClose }: CitationDrawerProps) {
  useEffect(() => {
    if (!citation) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [citation, onClose]);

  if (!citation) return null;
  return (
    <div className="citation-backdrop" onClick={onClose}>
      <aside
        aria-labelledby="citation-title"
        aria-modal="true"
        className="citation-drawer"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="citation-heading">
          <div>
            <p className="eyebrow">SOURCE {citation.source_id}</p>
            <h2 id="citation-title">资料原文</h2>
          </div>
          <button aria-label="关闭引用" onClick={onClose} type="button">×</button>
        </div>
        <dl>
          <div><dt>文档</dt><dd>{citation.document_name}</dd></div>
          <div><dt>页码</dt><dd>第 {citation.page_number} 页</dd></div>
        </dl>
        <blockquote>{citation.snippet}</blockquote>
      </aside>
    </div>
  );
}
