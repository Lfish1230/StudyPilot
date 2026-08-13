import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { QuizAttempt, QuizDetail } from "../../api/contracts";
import { QuizResultPage } from "./QuizResultPage";

export function QuizAttemptPage() {
  const { quizId } = useParams();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [result, setResult] = useState<QuizAttempt | null>(null);
  const quizQuery = useQuery({
    queryKey: ["quiz", quizId],
    queryFn: ({ signal }) => api.request<QuizDetail>(`/quizzes/${quizId}`, { signal }),
    enabled: Boolean(quizId),
  });
  const submitMutation = useMutation({
    mutationFn: () => api.request<QuizAttempt>(`/quizzes/${quizId}/submit`, {
      method: "POST",
      body: {
        answers: quizQuery.data!.questions.map((question) => ({
          question_id: question.id,
          answer: answers[question.id].trim(),
        })),
      },
    }),
    onSuccess: setResult,
    onError: (caught) => setError(
      caught instanceof ApiError ? caught.message : "提交失败，答案已保留，请重试。",
    ),
  });

  if (!quizId) return <Navigate replace to="../quizzes" />;
  if (quizQuery.isPending) return <main className="workspace-page">正在加载测验…</main>;
  if (quizQuery.isError || !quizQuery.data) return <main className="workspace-page state-card" role="alert">测验加载失败或不存在。</main>;
  if (result) return <QuizResultPage attempt={result} title={quizQuery.data.title} />;

  function submit(event: FormEvent) {
    event.preventDefault();
    const missing = quizQuery.data!.questions.some((question) => !answers[question.id]?.trim());
    if (missing) {
      setError("请回答所有题目后再提交。");
      return;
    }
    setError("");
    submitMutation.mutate();
  }

  return (
    <form className="workspace-page quiz-attempt" onSubmit={submit}>
      <header><p className="eyebrow">QUIZ ATTEMPT</p><h1>{quizQuery.data.title}</h1><p className="muted">共 {quizQuery.data.question_count} 题，提交后才能查看答案与解析。</p></header>
      {quizQuery.data.questions.map((question, index) => (
        <fieldset className="question-card" key={question.id}>
          <legend><span>第 {index + 1} 题 · {question.type === "multiple_choice" ? "选择题" : "简答题"}</span>{question.prompt}</legend>
          {question.type === "multiple_choice" ? (
            <div className="option-list">{question.options?.map((option) => (
              <label key={option}><input checked={answers[question.id] === option} name={question.id} onChange={() => setAnswers((current) => ({ ...current, [question.id]: option }))} type="radio" /><span>{option}</span></label>
            ))}</div>
          ) : (
            <textarea aria-label={`第 ${index + 1} 题答案`} onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))} placeholder="请输入你的回答" rows={5} value={answers[question.id] ?? ""} />
          )}
          <small>{question.knowledge_point} · {question.difficulty}</small>
        </fieldset>
      ))}
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button submit-quiz" disabled={submitMutation.isPending} type="submit">{submitMutation.isPending ? "正在评分…" : "提交测验"}</button>
    </form>
  );
}
