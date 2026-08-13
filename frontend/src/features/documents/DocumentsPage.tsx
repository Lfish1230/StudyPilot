import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { Course, CourseDocument } from "../../api/contracts";
import { DocumentStatus } from "./DocumentStatus";
import { UploadPanel } from "./UploadPanel";

function formatBytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentsPage() {
  const { courseId } = useParams();
  const { course } = useOutletContext<{ course: Course }>();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const documentsQuery = useQuery({
    queryKey: ["documents", courseId],
    queryFn: () => api.request<CourseDocument[]>(`/courses/${courseId}/documents`),
    enabled: Boolean(courseId),
    refetchInterval: (query) => {
      const documents = query.state.data;
      return documents?.some((item) => ["uploaded", "processing"].includes(item.status))
        ? 2000
        : false;
    },
  });
  const retryMutation = useMutation({
    mutationFn: (documentId: string) =>
      api.request<CourseDocument>(`/documents/${documentId}/retry`, { method: "POST" }),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["documents", courseId] });
    },
    onError: showActionError,
  });
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) =>
      api.request<void>(`/documents/${documentId}`, { method: "DELETE" }),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["documents", courseId] });
    },
    onError: showActionError,
  });

  function showActionError(caught: Error) {
    setActionError(
      caught instanceof ApiError ? caught.message : "操作失败，请稍后重试。",
    );
  }

  function handleUploaded(document: CourseDocument) {
    queryClient.setQueryData<CourseDocument[]>(
      ["documents", courseId],
      (current = []) => [document, ...current.filter((item) => item.id !== document.id)],
    );
  }

  function handleDelete(document: CourseDocument) {
    if (window.confirm(`确定删除“${document.original_name}”吗？`)) {
      deleteMutation.mutate(document.id);
    }
  }

  const documents = documentsQuery.data ?? [];
  return (
    <div className="workspace-page documents-page">
      <UploadPanel courseId={course.id} onUploaded={handleUploaded} />
      {actionError && <p className="form-error" role="alert">{actionError}</p>}
      <section className="document-list" aria-labelledby="document-list-title">
        <div className="list-heading">
          <div>
            <h2 id="document-list-title">已上传资料</h2>
            <p className="muted">处理完成后即可用于问答与测验。</p>
          </div>
          <span>{documents.length} 份</span>
        </div>
        {documentsQuery.isPending && <p className="state-card">正在加载资料…</p>}
        {documentsQuery.isError && (
          <div className="state-card" role="alert">
            <p>资料加载失败，请检查网络后重试。</p>
            <button onClick={() => documentsQuery.refetch()} type="button">重新加载</button>
          </div>
        )}
        {!documentsQuery.isPending && !documentsQuery.isError && documents.length === 0 && (
          <div className="state-card empty-state">
            <span aria-hidden="true">📄</span>
            <h2>还没有资料</h2>
            <p>上传一份文字版 PDF 开始建立课程知识库。</p>
          </div>
        )}
        <div className="document-items">
          {documents.map((document) => (
            <article className="document-item" key={document.id}>
              <div className="document-icon" aria-hidden="true">PDF</div>
              <div className="document-info">
                <div>
                  <h3>{document.original_name}</h3>
                  <DocumentStatus status={document.status} />
                </div>
                <p>
                  {formatBytes(document.size_bytes)}
                  {document.page_count ? ` · ${document.page_count} 页` : ""}
                </p>
                {document.status === "processing" && (
                  <p className="processing-note" aria-live="polite">正在解析文本并生成向量，请稍候…</p>
                )}
                {document.status === "failed" && (
                  <p className="document-failure" role="alert">
                    {document.failure_message ?? "文档处理失败，请重试。"}
                  </p>
                )}
              </div>
              <div className="document-actions">
                {document.status === "failed" && (
                  <button
                    disabled={retryMutation.isPending}
                    onClick={() => retryMutation.mutate(document.id)}
                    type="button"
                  >重试</button>
                )}
                <button
                  className="danger-button"
                  disabled={deleteMutation.isPending}
                  onClick={() => handleDelete(document)}
                  type="button"
                >删除</button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
