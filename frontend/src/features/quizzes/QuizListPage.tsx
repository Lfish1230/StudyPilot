import { useQuery } from "@tanstack/react-query";
import { Link, useOutletContext } from "react-router-dom";

import { api } from "../../api/client";
import type { Course, CourseDocument, QuizSummary } from "../../api/contracts";
import { QuizBuilder } from "./QuizBuilder";

export function QuizListPage() {
  const { course } = useOutletContext<{ course: Course }>();
  const quizzesQuery = useQuery({
    queryKey: ["quizzes", course.id],
    queryFn: ({ signal }) => api.request<QuizSummary[]>(`/courses/${course.id}/quizzes`, { signal }),
  });
  const documentsQuery = useQuery({
    queryKey: ["documents", course.id],
    queryFn: ({ signal }) => api.request<CourseDocument[]>(`/courses/${course.id}/documents`, { signal }),
  });
  return (
    <div className="workspace-page quiz-list-page">
      <QuizBuilder courseId={course.id} documents={documentsQuery.data ?? []} />
      <section className="quiz-history" aria-labelledby="quiz-history-title">
        <div className="list-heading"><div><h2 id="quiz-history-title">历史测验</h2><p className="muted">继续完成以前生成的练习。</p></div></div>
        {quizzesQuery.isPending && <p className="state-card">正在加载测验…</p>}
        {quizzesQuery.isError && <p className="state-card" role="alert">测验加载失败，请重试。</p>}
        {!quizzesQuery.isPending && !quizzesQuery.isError && !quizzesQuery.data?.length && (
          <div className="state-card empty-state"><span aria-hidden="true">✏️</span><h2>还没有测验</h2><p>选择课程资料生成第一组练习题。</p></div>
        )}
        <div className="quiz-cards">
          {quizzesQuery.data?.map((quiz) => (
            <article key={quiz.id}><div><span>共 {quiz.question_count} 题</span><h3>{quiz.title}</h3><p>{new Date(quiz.created_at).toLocaleDateString("zh-CN")}</p></div><Link className="primary-link" to={`./${quiz.id}`}>开始答题</Link></article>
          ))}
        </div>
      </section>
    </div>
  );
}
