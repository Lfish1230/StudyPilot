import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { api } from "../../api/client";
import type { Course, Mistake } from "../../api/contracts";

export function MistakesPage() {
  const { course } = useOutletContext<{ course: Course }>();
  const [knowledgePoint, setKnowledgePoint] = useState("全部");
  const mistakesQuery = useQuery({
    queryKey: ["mistakes", course.id],
    queryFn: ({ signal }) => api.request<Mistake[]>(`/courses/${course.id}/mistakes`, { signal }),
  });
  const points = useMemo(() => Array.from(new Set((mistakesQuery.data ?? []).map((item) => item.knowledge_point))), [mistakesQuery.data]);
  const mistakes = (mistakesQuery.data ?? []).filter((item) => knowledgePoint === "全部" || item.knowledge_point === knowledgePoint);
  return (
    <div className="workspace-page mistakes-page">
      <header className="page-heading"><div><p className="eyebrow">MISTAKE BOOK</p><h1>错题本</h1><p className="muted">回顾失分题目和 AI 反馈，针对薄弱点复习。</p></div><label>知识点筛选<select onChange={(event) => setKnowledgePoint(event.target.value)} value={knowledgePoint}><option>全部</option>{points.map((point) => <option key={point}>{point}</option>)}</select></label></header>
      {mistakesQuery.isPending && <p className="state-card">正在加载错题…</p>}
      {mistakesQuery.isError && <p className="state-card" role="alert">错题加载失败，请重试。</p>}
      {!mistakesQuery.isPending && !mistakesQuery.isError && mistakes.length === 0 && <div className="state-card empty-state"><span aria-hidden="true">🎉</span><h2>暂时没有错题</h2><p>完成测验后，失分题目会自动汇总到这里。</p></div>}
      <div className="mistake-list">{mistakes.map((mistake) => (
        <article key={`${mistake.attempt_id}-${mistake.question_id}`}>
          <header><span>{mistake.quiz_title}</span><strong>{mistake.score}/10 分</strong></header><h2>{mistake.prompt}</h2>
          <dl><div><dt>你的答案</dt><dd>{mistake.user_answer}</dd></div><div><dt>参考答案</dt><dd>{mistake.standard_answer}</dd></div><div><dt>解析</dt><dd>{mistake.explanation}</dd></div><div><dt>反馈</dt><dd>{mistake.feedback}</dd></div></dl>
          {mistake.missing_points.length > 0 && <p>遗漏要点：{mistake.missing_points.join("、")}</p>}
          <footer><span>{mistake.knowledge_point}</span><Link to="../documents">来源：{mistake.source_document_name} · 第 {mistake.source_page} 页</Link></footer>
        </article>
      ))}</div>
    </div>
  );
}
