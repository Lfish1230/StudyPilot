import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type {
  Conversation,
  ConversationMessage,
  Course,
  CourseAnalytics,
  CourseDocument,
  MessageCitation,
} from "../../api/contracts";
import { ChatComposer } from "./ChatComposer";
import { CitationDrawer } from "./CitationDrawer";
import { MessageList } from "./MessageList";

export function ChatPage() {
  const { courseId } = useParams();
  const { course } = useOutletContext<{ course: Course }>();
  const queryClient = useQueryClient();
  const requestController = useRef<AbortController | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isNewConversation, setIsNewConversation] = useState(false);
  const [draft, setDraft] = useState("");
  const [optimisticQuestion, setOptimisticQuestion] = useState("");
  const [error, setError] = useState("");
  const [citation, setCitation] = useState<MessageCitation | null>(null);

  const conversationsQuery = useQuery({
    queryKey: ["conversations", courseId],
    queryFn: ({ signal }) =>
      api.request<Conversation[]>(`/courses/${courseId}/conversations`, { signal }),
    enabled: Boolean(courseId),
  });
  const messagesQuery = useQuery({
    queryKey: ["messages", activeConversationId],
    queryFn: ({ signal }) =>
      api.request<ConversationMessage[]>(`/conversations/${activeConversationId}/messages`, {
        signal,
      }),
    enabled: Boolean(activeConversationId),
  });
  const documentsQuery = useQuery({
    queryKey: ["documents", courseId],
    queryFn: ({ signal }) =>
      api.request<CourseDocument[]>(`/courses/${courseId}/documents`, { signal }),
    enabled: Boolean(courseId),
  });
  const analyticsQuery = useQuery({
    queryKey: ["analytics", courseId],
    queryFn: ({ signal }) =>
      api.request<CourseAnalytics>(`/courses/${courseId}/analytics`, { signal }),
    enabled: Boolean(courseId),
  });

  useEffect(() => {
    if (!isNewConversation && !activeConversationId && conversationsQuery.data?.length) {
      setActiveConversationId(conversationsQuery.data[0].id);
    }
  }, [activeConversationId, conversationsQuery.data, isNewConversation]);

  useEffect(() => {
    setActiveConversationId(null);
    setIsNewConversation(false);
    setDraft("");
    setOptimisticQuestion("");
    setError("");
    setCitation(null);
    return () => requestController.current?.abort();
  }, [courseId]);

  const sendMutation = useMutation({
    mutationFn: async (question: string) => {
      const controller = new AbortController();
      requestController.current = controller;
      let conversationId = activeConversationId;
      if (!conversationId) {
        const conversation = await api.request<Conversation>(
          `/courses/${course.id}/conversations`,
          { method: "POST", signal: controller.signal },
        );
        conversationId = conversation.id;
        setActiveConversationId(conversation.id);
        setIsNewConversation(false);
        queryClient.setQueryData<Conversation[]>(
          ["conversations", courseId],
          (current = []) => [conversation, ...current],
        );
      }
      const answer = await api.request<ConversationMessage>(
        `/conversations/${conversationId}/messages`,
        { method: "POST", body: { question }, signal: controller.signal },
      );
      return { answer, conversationId };
    },
    onSuccess: async ({ conversationId }) => {
      setError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["messages", conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["conversations", courseId] }),
      ]);
      setOptimisticQuestion("");
    },
    onError: (caught, question) => {
      setDraft(question);
      setOptimisticQuestion("");
      if (caught instanceof ApiError && caught.status === 429) {
        setError("今天的资料问答次数已用完，请明天再试。");
      } else if (caught instanceof ApiError) {
        setError(caught.message);
      } else if ((caught as Error).name !== "AbortError") {
        setError("网络连接失败，问题已保留，请重试。");
      }
    },
    onSettled: () => {
      requestController.current = null;
    },
  });

  function sendQuestion() {
    const question = draft.trim();
    if (!question || sendMutation.isPending) return;
    setError("");
    setDraft("");
    setOptimisticQuestion(question);
    sendMutation.mutate(question);
  }

  function startNewConversation() {
    if (sendMutation.isPending) return;
    setActiveConversationId(null);
    setIsNewConversation(true);
    setError("");
    setOptimisticQuestion("");
  }

  const readyDocuments = (documentsQuery.data ?? []).filter((item) => item.status === "ready");
  const messages = activeConversationId ? (messagesQuery.data ?? []) : [];
  return (
    <div className="chat-page">
      <section className="chat-main" aria-label="课程问答">
        <header className="chat-header">
          <div>
            <p className="eyebrow">GROUNDED Q&amp;A</p>
            <h1>{course.name}问答</h1>
          </div>
          <div className="conversation-controls">
            <label htmlFor="conversation-select">历史对话</label>
            <select
              disabled={!conversationsQuery.data?.length || sendMutation.isPending}
              id="conversation-select"
              onChange={(event) => {
                setActiveConversationId(event.target.value);
                setIsNewConversation(false);
              }}
              value={activeConversationId ?? ""}
            >
              {isNewConversation && <option value="">新对话</option>}
              {!conversationsQuery.data?.length && <option value="">暂无历史对话</option>}
              {conversationsQuery.data?.map((item, index) => (
                <option key={item.id} value={item.id}>对话 {conversationsQuery.data.length - index}</option>
              ))}
            </select>
            <button onClick={startNewConversation} type="button">＋ 新对话</button>
          </div>
        </header>
        <MessageList
          isLoading={Boolean(activeConversationId) && messagesQuery.isPending}
          isSending={sendMutation.isPending}
          messages={messages}
          onCitationClick={setCitation}
          optimisticQuestion={optimisticQuestion}
        />
        {error && <p className="chat-error" role="alert">{error}</p>}
        <ChatComposer
          draft={draft}
          isSending={sendMutation.isPending}
          onDraftChange={setDraft}
          onSend={sendQuestion}
        />
      </section>

      <aside className="chat-context" aria-label="课程概览">
        <section>
          <div className="context-heading"><h2>可用资料</h2><Link to="../documents">管理</Link></div>
          {readyDocuments.length === 0 ? (
            <p className="muted">暂无处理完成的 PDF，请先上传课程资料。</p>
          ) : (
            <ul>{readyDocuments.map((item) => <li key={item.id}>📄 {item.original_name}</li>)}</ul>
          )}
        </section>
        <section className="quiz-callout">
          <span aria-hidden="true">✏️</span>
          <h2>检验学习效果</h2>
          <p>根据课程资料生成一组练习题。</p>
          <Link className="primary-link" to="../quizzes">生成测验</Link>
        </section>
        <section>
          <div className="context-heading"><h2>学习概览</h2><Link to="../analytics">详情</Link></div>
          <div className="analytics-mini">
            <div><strong>{analyticsQuery.data?.total_attempts ?? 0}</strong><span>测验次数</span></div>
            <div><strong>{Math.round(analyticsQuery.data?.average_percent_score ?? 0)}%</strong><span>平均得分</span></div>
          </div>
          {analyticsQuery.data?.weak_topics[0] && (
            <p className="weak-topic">待加强：{analyticsQuery.data.weak_topics[0].knowledge_point}</p>
          )}
        </section>
      </aside>
      <CitationDrawer citation={citation} onClose={() => setCitation(null)} />
    </div>
  );
}
