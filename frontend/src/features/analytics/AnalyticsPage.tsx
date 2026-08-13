import { useQuery } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";

import { api } from "../../api/client";
import type { Course, CourseAnalytics } from "../../api/contracts";

function safePercent(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 0;
}

export function AnalyticsPage() {
  const { course } = useOutletContext<{ course: Course }>();
  const analyticsQuery = useQuery({
    queryKey: ["analytics", course.id],
    queryFn: ({ signal }) => api.request<CourseAnalytics>(`/courses/${course.id}/analytics`, { signal }),
  });
  if (analyticsQuery.isPending) return <main className="workspace-page">正在加载学习分析…</main>;
  if (analyticsQuery.isError || !analyticsQuery.data) return <main className="workspace-page state-card" role="alert">学习分析加载失败，请重试。</main>;
  const analytics = analyticsQuery.data;
  const hasActivity = analytics.total_attempts > 0 || analytics.total_questions > 0;
  return (
    <div className="workspace-page analytics-page">
      <header><p className="eyebrow">LEARNING ANALYTICS</p><h1>学习分析</h1><p className="muted">用测验数据定位薄弱知识点，安排下一轮复习。</p></header>
      {!hasActivity ? <div className="state-card empty-state" role="status"><span aria-hidden="true">📊</span><h2>还没有学习数据</h2><p>完成第一次测验后，这里会展示得分趋势和薄弱知识点。</p></div> : <>
        <section className="metric-grid" aria-label="学习数据概览"><article><span>测验次数</span><strong>{analytics.total_attempts}</strong></article><article><span>已答题目</span><strong>{analytics.total_questions}</strong></article><article><span>平均得分</span><strong>{safePercent(analytics.average_percent_score)}%</strong></article></section>
        <section className="analytics-section" aria-labelledby="weak-topics-title"><div className="list-heading"><div><h2 id="weak-topics-title">薄弱知识点</h2><p className="muted">分数越高，越需要优先复习。</p></div></div>
          {analytics.weak_topics.length === 0 ? <p className="muted">暂无薄弱知识点。</p> : <div className="weak-table-wrap"><table><thead><tr><th scope="col">知识点</th><th scope="col">答题数</th><th scope="col">错题数</th><th scope="col">薄弱程度</th></tr></thead><tbody>{analytics.weak_topics.map((topic) => <tr key={topic.knowledge_point}><th scope="row">{topic.knowledge_point}</th><td>{topic.answered_count}</td><td>{topic.wrong_count}</td><td><div className="weak-bar" aria-label={`薄弱程度 ${safePercent(topic.weak_score)}%`}><span style={{ width: `${safePercent(topic.weak_score)}%` }} /></div><strong>{safePercent(topic.weak_score)}%</strong></td></tr>)}</tbody></table></div>}
        </section>
        <section className="analytics-section" aria-labelledby="recent-attempts-title"><div className="list-heading"><div><h2 id="recent-attempts-title">最近测验</h2></div></div><div className="recent-attempts">{analytics.recent_attempts.map((attempt) => <article key={attempt.attempt_id}><div><h3>{attempt.quiz_title}</h3><p>{new Date(attempt.submitted_at).toLocaleString("zh-CN")}</p></div><strong>{safePercent(attempt.percentage)}%</strong><span>{attempt.total_score}/{attempt.max_score} 分</span></article>)}</div></section>
      </>}
    </div>
  );
}
