import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "../../App";
import { router } from "../../app/router";
import { server } from "../../test/server";

const apiUrl = "http://localhost:8000";
const courseId = "course-1";
const quizId = "quiz-1";
const user = { id: "user-1", email: "student@example.com", created_at: "2026-08-13T00:00:00Z" };
const course = { id: courseId, name: "计算机网络", created_at: "2026-08-10T00:00:00Z", updated_at: "2026-08-10T00:00:00Z" };
const readyDocument = { id: "ready-document", course_id: courseId, original_name: "network.pdf", size_bytes: 1024, page_count: 8, status: "ready", failure_code: null, failure_message: null, created_at: "2026-08-13T00:00:00Z", updated_at: "2026-08-13T00:00:00Z" };
const processingDocument = { ...readyDocument, id: "processing-document", original_name: "processing.pdf", status: "processing" };
const quiz = {
  id: quizId,
  course_id: courseId,
  title: "网络基础测验",
  question_count: 2,
  created_at: "2026-08-13T00:00:00Z",
  questions: [
    { id: "question-1", type: "multiple_choice", position: 1, prompt: "TCP 位于哪一层？", options: ["传输层", "网络层", "应用层", "数据链路层"], knowledge_point: "TCP", difficulty: "easy", source_document_id: readyDocument.id, source_document_name: "network.pdf", source_page: 1 },
    { id: "question-2", type: "short_answer", position: 2, prompt: "简述三次握手的作用。", options: null, knowledge_point: "TCP 握手", difficulty: "medium", source_document_id: readyDocument.id, source_document_name: "network.pdf", source_page: 2 },
  ],
};
const attempt = {
  id: "attempt-1",
  quiz_id: quizId,
  total_score: 17,
  max_score: 20,
  percentage: 85,
  submitted_at: "2026-08-13T01:00:00Z",
  answers: [
    { question_id: "question-1", type: "multiple_choice", prompt: "TCP 位于哪一层？", user_answer: "传输层", standard_answer: "传输层", explanation: "TCP 是传输层协议。", score: 10, is_correct: true, feedback: "回答正确。", missing_points: [], knowledge_point: "TCP", source_document_id: readyDocument.id, source_document_name: "network.pdf", source_page: 1 },
    { question_id: "question-2", type: "short_answer", prompt: "简述三次握手的作用。", user_answer: "确认发送能力", standard_answer: "确认双方收发能力。", explanation: "握手确认通信双方的收发能力。", score: 7, is_correct: false, feedback: "基本正确。", missing_points: ["接收能力"], knowledge_point: "TCP 握手", source_document_id: readyDocument.id, source_document_name: "network.pdf", source_page: 2 },
  ],
};

function commonHandlers() {
  server.use(
    http.get(`${apiUrl}/auth/me`, () => HttpResponse.json(user)),
    http.get(`${apiUrl}/courses/${courseId}`, () => HttpResponse.json(course)),
  );
}

async function open(path: string) {
  sessionStorage.setItem("studypilot_access_token", "test-token");
  commonHandlers();
  await router.navigate(path);
  return render(<App />);
}

describe("quiz learning flow", () => {
  it("offers only ready documents and enforces question-count limits", async () => {
    const actor = userEvent.setup();
    server.use(
      http.get(`${apiUrl}/courses/${courseId}/documents`, () => HttpResponse.json([readyDocument, processingDocument])),
      http.get(`${apiUrl}/courses/${courseId}/quizzes`, () => HttpResponse.json([])),
    );
    await open(`/courses/${courseId}/quizzes`);
    expect(await screen.findByRole("checkbox", { name: /network.pdf/ })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /processing.pdf/ })).not.toBeInTheDocument();

    const counts = screen.getAllByRole("spinbutton");
    await actor.clear(counts[0]);
    await actor.type(counts[0], "10");
    await actor.clear(counts[1]);
    await actor.type(counts[1], "1");
    await actor.click(screen.getByRole("checkbox", { name: /network.pdf/ }));
    await actor.click(screen.getByRole("button", { name: "生成测验" }));
    expect(screen.getByRole("alert")).toHaveTextContent("题目总数不能超过 10 道");
  });

  it("shows a dedicated quota error while preserving selections", async () => {
    const actor = userEvent.setup();
    server.use(
      http.get(`${apiUrl}/courses/${courseId}/documents`, () => HttpResponse.json([readyDocument])),
      http.get(`${apiUrl}/courses/${courseId}/quizzes`, () => HttpResponse.json([])),
      http.post(`${apiUrl}/courses/${courseId}/quizzes`, () => HttpResponse.json({ code: "quiz_quota_exceeded", message: "quota", request_id: "r1" }, { status: 429 })),
    );
    await open(`/courses/${courseId}/quizzes`);
    const checkbox = await screen.findByRole("checkbox", { name: /network.pdf/ });
    await actor.click(checkbox);
    await actor.click(screen.getByRole("button", { name: "生成测验" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("今天的 AI 测验生成次数已用完");
    expect(checkbox).toBeChecked();
  });

  it("requires every answer, hides solutions before submit, and renders immutable results", async () => {
    const actor = userEvent.setup();
    let submitCalls = 0;
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    server.use(
      http.get(`${apiUrl}/quizzes/${quizId}`, () => HttpResponse.json(quiz)),
      http.post(`${apiUrl}/quizzes/${quizId}/submit`, async () => {
        submitCalls += 1;
        await gate;
        return HttpResponse.json(attempt);
      }),
    );
    await open(`/courses/${courseId}/quizzes/${quizId}`);
    expect(await screen.findByText("TCP 位于哪一层？")).toBeInTheDocument();
    expect(screen.queryByText("参考答案")).not.toBeInTheDocument();
    expect(screen.queryByText("TCP 是传输层协议。")).not.toBeInTheDocument();

    await actor.click(screen.getByRole("radio", { name: "传输层" }));
    await actor.click(screen.getByRole("button", { name: "提交测验" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请回答所有题目");
    expect(submitCalls).toBe(0);

    await actor.type(screen.getByLabelText("第 2 题答案"), "确认发送能力");
    await actor.click(screen.getByRole("button", { name: "提交测验" }));
    expect(await screen.findByRole("button", { name: "正在评分…" })).toBeDisabled();
    await actor.click(screen.getByRole("button", { name: "正在评分…" }));
    expect(submitCalls).toBe(1);
    release();

    expect(await screen.findByLabelText("得分 85%")).toBeInTheDocument();
    expect(screen.getAllByText("参考答案")).toHaveLength(2);
    expect(screen.getByText("TCP 是传输层协议。")).toBeInTheDocument();
    expect(screen.getByText("确认双方收发能力。")).toBeInTheDocument();
    expect(screen.getByText("遗漏要点：接收能力")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "来源：network.pdf · 第 2 页" })).toHaveAttribute(
      "href",
      `/courses/${courseId}/documents`,
    );
    expect(screen.queryByRole("button", { name: "提交测验" })).not.toBeInTheDocument();
  });

  it("renders an accessible empty mistake book", async () => {
    server.use(http.get(`${apiUrl}/courses/${courseId}/mistakes`, () => HttpResponse.json([])));
    await open(`/courses/${courseId}/mistakes`);
    expect(await screen.findByRole("heading", { name: "暂时没有错题" })).toBeInTheDocument();
    expect(screen.getByText("失分题目会自动汇总到这里", { exact: false })).toBeInTheDocument();
  });
});
