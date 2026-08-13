import { useRef, useState, type ChangeEvent } from "react";

import { ApiError, uploadFile } from "../../api/client";
import type { CourseDocument } from "../../api/contracts";

const MAX_PDF_BYTES = 20 * 1024 * 1024;

interface UploadPanelProps {
  courseId: string;
  onUploaded(document: CourseDocument): void;
}

export function UploadPanel({ courseId, onUploaded }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.type !== "application/pdf" || !file.name.toLowerCase().endsWith(".pdf")) {
      setError("仅支持 PDF 文件。");
      return;
    }
    if (file.size > MAX_PDF_BYTES) {
      setError("PDF 文件不能超过 20 MB。");
      return;
    }
    setError("");
    setProgress(0);
    try {
      const document = await uploadFile<CourseDocument>(
        `/courses/${courseId}/documents`,
        file,
        setProgress,
      );
      onUploaded(document);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "上传失败，请重试。");
    } finally {
      setProgress(null);
    }
  }

  return (
    <section className="upload-panel" aria-labelledby="upload-title">
      <div>
        <p className="eyebrow">COURSE MATERIALS</p>
        <h1 id="upload-title">课程资料</h1>
        <p className="muted">上传文字版 PDF，系统会自动解析并建立可检索的知识库。</p>
      </div>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept="application/pdf,.pdf"
        aria-label="选择 PDF 文件"
        onChange={handleFile}
      />
      <button
        className="primary-button"
        disabled={progress !== null}
        onClick={() => inputRef.current?.click()}
        type="button"
      >
        {progress !== null ? "上传中…" : "上传 PDF"}
      </button>
      {progress !== null && (
        <div className="upload-progress" aria-live="polite">
          <div><span style={{ width: `${progress}%` }} /></div>
          <strong>{progress}%</strong>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
