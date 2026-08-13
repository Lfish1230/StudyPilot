import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { CourseDocument, QuizDetail } from "../../api/contracts";

interface QuizBuilderProps {
  courseId: string;
  documents: CourseDocument[];
}

export function QuizBuilder({ courseId, documents }: QuizBuilderProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const readyDocuments = useMemo(
    () => documents.filter((document) => document.status === "ready"),
    [documents],
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [multipleChoiceCount, setMultipleChoiceCount] = useState(3);
  const [shortAnswerCount, setShortAnswerCount] = useState(1);
  const [error, setError] = useState("");
  const total = multipleChoiceCount + shortAnswerCount;
  const createMutation = useMutation({
    mutationFn: () =>
      api.request<QuizDetail>(`/courses/${courseId}/quizzes`, {
        method: "POST",
        body: {
          document_ids: selected,
          multiple_choice_count: multipleChoiceCount,
          short_answer_count: shortAnswerCount,
        },
      }),
    onSuccess: async (quiz) => {
      await queryClient.invalidateQueries({ queryKey: ["quizzes", courseId] });
      navigate(`./${quiz.id}`);
    },
    onError: (caught) => {
      if (caught instanceof ApiError && caught.status === 429) {
        setError("今天的 AI 测验生成次数已用完，请明天再试。");
      } else {
        setError(caught instanceof ApiError ? caught.message : "测验生成失败，请重试。");
      }
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (selected.length === 0) {
      setError("请至少选择一份已处理完成的资料。");
      return;
    }
    if (multipleChoiceCount < 1 || shortAnswerCount < 0 || total > 10) {
      setError("选择题至少 1 道，题目总数不能超过 10 道。");
      return;
    }
    setError("");
    createMutation.mutate();
  }

  return (
    <form className="quiz-builder" onSubmit={submit}>
      <div className="quiz-builder-heading">
        <div><p className="eyebrow">AI QUIZ</p><h1>生成新测验</h1></div>
        <span>{total}/10 题</span>
      </div>
      <fieldset>
        <legend>选择出题资料</legend>
        {readyDocuments.length === 0 ? (
          <p className="muted">暂无可用资料，请先等待 PDF 处理完成。</p>
        ) : readyDocuments.map((document) => (
          <label className="document-choice" key={document.id}>
            <input
              checked={selected.includes(document.id)}
              onChange={(event) => setSelected((current) =>
                event.target.checked
                  ? [...current, document.id]
                  : current.filter((id) => id !== document.id),
              )}
              type="checkbox"
            />
            <span>📄 {document.original_name}</span>
          </label>
        ))}
      </fieldset>
      <div className="question-counts">
        <label>选择题
          <input max={10} min={1} onChange={(event) => setMultipleChoiceCount(Number(event.target.value))} type="number" value={multipleChoiceCount} />
        </label>
        <label>简答题
          <input max={5} min={0} onChange={(event) => setShortAnswerCount(Number(event.target.value))} type="number" value={shortAnswerCount} />
        </label>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" disabled={createMutation.isPending || readyDocuments.length === 0} type="submit">
        {createMutation.isPending ? "正在生成…" : "生成测验"}
      </button>
    </form>
  );
}
