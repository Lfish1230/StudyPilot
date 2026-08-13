import { Link } from "react-router-dom";

import type { QuizAttempt } from "../../api/contracts";

export function QuizResultPage({ attempt, title }: { attempt: QuizAttempt; title: string }) {
  const percentage = Number.isFinite(attempt.percentage) ? Math.round(attempt.percentage) : 0;
  return (
    <div className="workspace-page quiz-result">
      <header className="result-summary">
        <div><p className="eyebrow">QUIZ RESULT</p><h1>{title}</h1><p>已完成 · {new Date(attempt.submitted_at).toLocaleString("zh-CN")}</p></div>
        <div className="score-ring" aria-label={`得分 ${percentage}%`}><strong>{percentage}%</strong><span>{attempt.total_score}/{attempt.max_score} 分</span></div>
      </header>
      <div className="answer-results">
        {attempt.answers.map((answer, index) => (
          <article className={answer.is_correct ? "answer-correct" : "answer-wrong"} key={answer.question_id}>
            <header><span>{answer.is_correct ? "✓ 正确" : "需加强"}</span><strong>{answer.score}/10 分</strong></header>
            <h2>{index + 1}. {answer.prompt}</h2>
            <dl>
              <div><dt>你的答案</dt><dd>{answer.user_answer}</dd></div>
              <div><dt>参考答案</dt><dd>{answer.standard_answer}</dd></div>
              <div><dt>解析</dt><dd>{answer.explanation}</dd></div>
              <div><dt>反馈</dt><dd>{answer.feedback}</dd></div>
            </dl>
            {answer.missing_points.length > 0 && <p className="missing-points">遗漏要点：{answer.missing_points.join("、")}</p>}
            <p className="answer-source">
              <Link to="../documents">来源：{answer.source_document_name} · 第 {answer.source_page} 页</Link>
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
