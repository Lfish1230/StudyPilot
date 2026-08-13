import { http, HttpResponse } from "msw";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../../App";
import { router } from "../../app/router";
import { server } from "../../test/server";

const apiUrl = "http://localhost:8000";
const courseId = "course-1";

async function openAnalytics(payload: object) {
  sessionStorage.setItem("studypilot_access_token", "test-token");
  server.use(
    http.get(`${apiUrl}/auth/me`, () => HttpResponse.json({ id: "user-1", email: "student@example.com", created_at: "2026-08-13T00:00:00Z" })),
    http.get(`${apiUrl}/courses/${courseId}`, () => HttpResponse.json({ id: courseId, name: "计算机网络", created_at: "2026-08-10T00:00:00Z", updated_at: "2026-08-10T00:00:00Z" })),
    http.get(`${apiUrl}/courses/${courseId}/analytics`, () => HttpResponse.json(payload)),
  );
  await router.navigate(`/courses/${courseId}/analytics`);
  return render(<App />);
}

describe("learning analytics", () => {
  it("shows metrics, ordered weak topics, bars, and recent attempts", async () => {
    await openAnalytics({
      total_questions: 12,
      total_attempts: 3,
      average_percent_score: 76.4,
      weak_topics: [
        { knowledge_point: "拥塞控制", answered_count: 4, wrong_count: 3, weak_score: 75 },
        { knowledge_point: "TCP 握手", answered_count: 5, wrong_count: 2, weak_score: 40 },
      ],
      recent_attempts: [
        { attempt_id: "attempt-1", quiz_id: "quiz-1", quiz_title: "网络测验", total_score: 17, max_score: 20, percentage: 85, submitted_at: "2026-08-13T01:00:00Z" },
      ],
    });
    const overview = await screen.findByRole("region", { name: "学习数据概览" });
    expect(within(overview).getByText("12")).toBeInTheDocument();
    expect(within(overview).getByText("3")).toBeInTheDocument();
    expect(within(overview).getByText("76%")).toBeInTheDocument();
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("拥塞控制");
    expect(rows[2]).toHaveTextContent("TCP 握手");
    expect(screen.getByLabelText("薄弱程度 75%")).toBeInTheDocument();
    expect(screen.getByText("网络测验")).toBeInTheDocument();
    expect(screen.getByText("17/20 分")).toBeInTheDocument();
  });

  it("has an accessible empty state and never renders NaN", async () => {
    await openAnalytics({ total_questions: 0, total_attempts: 0, average_percent_score: 0, weak_topics: [], recent_attempts: [] });
    expect(await screen.findByRole("status")).toHaveTextContent("还没有学习数据");
    expect(document.body).not.toHaveTextContent("NaN");
  });
});
