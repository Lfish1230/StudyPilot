import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import App from "../../App";
import { router } from "../../app/router";
import type { ConversationMessage } from "../../api/contracts";
import { server } from "../../test/server";

const apiUrl = "http://localhost:8000";
const courseId = "course-1";
const conversationId = "conversation-1";
const currentUser = {
  id: "user-1",
  email: "student@example.com",
  created_at: "2026-08-13T00:00:00Z",
};
const course = {
  id: courseId,
  name: "计算机网络",
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
};
const conversation = {
  id: conversationId,
  course_id: courseId,
  created_at: "2026-08-13T00:00:00Z",
  updated_at: "2026-08-13T00:00:00Z",
};
const userMessage: ConversationMessage = {
  id: "message-user",
  role: "user",
  content: "TCP 为什么需要三次握手？",
  refused: false,
  model: null,
  input_tokens: 0,
  output_tokens: 0,
  latency_ms: null,
  citations: [],
  created_at: "2026-08-13T00:01:00Z",
};
const citedAnswer: ConversationMessage = {
  id: "message-assistant",
  role: "assistant",
  content: "三次握手用于确认双方具备收发能力。[S1]",
  refused: false,
  model: "fake-chat",
  input_tokens: 30,
  output_tokens: 12,
  latency_ms: 120,
  citations: [
    {
      source_id: "S1",
      document_id: "document-1",
      document_name: "计算机网络.pdf",
      page_number: 2,
      snippet: "TCP 三次握手可以确认通信双方的收发能力。",
    },
  ],
  created_at: "2026-08-13T00:01:01Z",
};

async function openChat(
  conversations = [] as typeof conversation[],
  messages = [] as ConversationMessage[],
  useDefaultMessageHandler = true,
) {
  sessionStorage.setItem("studypilot_access_token", "test-token");
  server.use(
    http.get(`${apiUrl}/auth/me`, () => HttpResponse.json(currentUser)),
    http.get(`${apiUrl}/courses/${courseId}`, () => HttpResponse.json(course)),
    http.get(`${apiUrl}/courses/${courseId}/conversations`, () =>
      HttpResponse.json(conversations),
    ),
    http.get(`${apiUrl}/courses/${courseId}/documents`, () =>
      HttpResponse.json([
        {
          id: "document-1",
          course_id: courseId,
          original_name: "计算机网络.pdf",
          size_bytes: 1024,
          page_count: 10,
          status: "ready",
          failure_code: null,
          failure_message: null,
          created_at: "2026-08-13T00:00:00Z",
          updated_at: "2026-08-13T00:00:00Z",
        },
      ]),
    ),
    http.get(`${apiUrl}/courses/${courseId}/analytics`, () =>
      HttpResponse.json({
        total_questions: 5,
        total_attempts: 2,
        average_percent_score: 80,
        weak_topics: [],
        recent_attempts: [],
      }),
    ),
  );
  if (useDefaultMessageHandler) {
    server.use(
      http.get(`${apiUrl}/conversations/${conversationId}/messages`, () =>
        HttpResponse.json(messages),
      ),
    );
  }
  await router.navigate(`/courses/${courseId}/chat`);
  return render(<App />);
}

describe("cited course chat", () => {
  beforeEach(() => {
    sessionStorage.setItem("studypilot_access_token", "test-token");
  });

  it("keeps the empty composer disabled and creates no conversation", async () => {
    let createCalls = 0;
    server.use(
      http.post(`${apiUrl}/courses/${courseId}/conversations`, () => {
        createCalls += 1;
        return HttpResponse.json(conversation, { status: 201 });
      }),
    );
    await openChat();
    expect(await screen.findByRole("button", { name: "发送问题" })).toBeDisabled();
    expect(createCalls).toBe(0);
  });

  it("shows an optimistic question, locks sending, and renders cited answer", async () => {
    const user = userEvent.setup();
    let releaseAnswer!: () => void;
    let sendCalls = 0;
    let history: ConversationMessage[] = [];
    const answerGate = new Promise<void>((resolve) => { releaseAnswer = resolve; });
    server.use(
      http.post(`${apiUrl}/courses/${courseId}/conversations`, () =>
        HttpResponse.json(conversation, { status: 201 }),
      ),
      http.get(`${apiUrl}/conversations/${conversationId}/messages`, () =>
        HttpResponse.json(history),
      ),
      http.post(`${apiUrl}/conversations/${conversationId}/messages`, async () => {
        sendCalls += 1;
        await answerGate;
        history = [userMessage, citedAnswer];
        return HttpResponse.json(citedAnswer, { status: 201 });
      }),
    );
    await openChat([], [], false);
    const input = await screen.findByLabelText("向课程资料提问");
    await user.type(input, userMessage.content);
    await user.click(screen.getByRole("button", { name: "发送问题" }));

    expect(await screen.findByText(userMessage.content)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("正在检索资料");
    expect(screen.getByRole("button", { name: "回答中…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "回答中…" }));
    expect(sendCalls).toBe(1);

    releaseAnswer();
    expect(await screen.findByText(/三次握手用于确认双方/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看引用 1" })).toHaveTextContent("[1]");
  });

  it("renders refusal as plain text and opens citation details", async () => {
    const user = userEvent.setup();
    const refusal = {
      ...citedAnswer,
      id: "refusal",
      content: "现有资料不足以回答这个问题。<script>alert('x')</script>",
      refused: true,
      citations: [],
    };
    await openChat([conversation], [refusal, citedAnswer]);
    expect(await screen.findByText("资料不足")).toBeInTheDocument();
    expect(screen.getByText(/<script>alert/)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();

    await user.click(screen.getByRole("button", { name: "查看引用 1" }));
    const drawer = screen.getByRole("dialog", { name: "资料原文" });
    expect(drawer).toHaveTextContent("计算机网络.pdf");
    expect(drawer).toHaveTextContent("第 2 页");
    expect(drawer).toHaveTextContent("TCP 三次握手可以确认通信双方的收发能力。");
  });

  it("restores the draft after a network failure so the question can retry", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${apiUrl}/courses/${courseId}/conversations`, () =>
        HttpResponse.json(conversation, { status: 201 }),
      ),
      http.post(`${apiUrl}/conversations/${conversationId}/messages`, () =>
        HttpResponse.error(),
      ),
    );
    await openChat();
    const input = await screen.findByLabelText("向课程资料提问");
    await user.type(input, "请解释拥塞控制");
    await user.click(screen.getByRole("button", { name: "发送问题" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("问题已保留");
    expect(input).toHaveValue("请解释拥塞控制");
    expect(screen.getByRole("button", { name: "发送问题" })).toBeEnabled();
  });

  it("shows a dedicated daily quota message for 429 responses", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${apiUrl}/courses/${courseId}/conversations`, () =>
        HttpResponse.json(conversation, { status: 201 }),
      ),
      http.post(`${apiUrl}/conversations/${conversationId}/messages`, () =>
        HttpResponse.json(
          {
            code: "question_quota_exceeded",
            message: "今天的资料问答次数已用完，请明天再试。",
            request_id: "request-1",
          },
          { status: 429 },
        ),
      ),
    );
    await openChat();
    const input = await screen.findByLabelText("向课程资料提问");
    await user.type(input, "继续提问");
    await user.click(screen.getByRole("button", { name: "发送问题" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "今天的资料问答次数已用完，请明天再试。",
    );
  });
});
