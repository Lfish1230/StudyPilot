import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import { router } from "../../app/router";
import { server } from "../../test/server";

const apiUrl = "http://localhost:8000";
const courseId = "course-1";
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
const readyDocument = {
  id: "document-ready",
  course_id: courseId,
  original_name: "network.pdf",
  size_bytes: 1024,
  page_count: 12,
  status: "ready",
  failure_code: null,
  failure_message: null,
  created_at: "2026-08-13T00:00:00Z",
  updated_at: "2026-08-13T00:00:00Z",
};

class MockXMLHttpRequest {
  static response = readyDocument;
  static status = 201;
  static sentFile: File | undefined;
  upload = new EventTarget();
  status = 0;
  responseText = "";
  private listeners = new Map<string, EventListener[]>();

  open() {}
  setRequestHeader() {}
  getResponseHeader() { return null; }
  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  send(body: FormData) {
    MockXMLHttpRequest.sentFile = body.get("file") as File;
    const progress = new ProgressEvent("progress", {
      lengthComputable: true,
      loaded: 5,
      total: 10,
    });
    this.upload.dispatchEvent(progress);
    setTimeout(() => {
      this.status = MockXMLHttpRequest.status;
      this.responseText = JSON.stringify(MockXMLHttpRequest.response);
      for (const listener of this.listeners.get("load") ?? []) {
        listener.call(this, new Event("load"));
      }
    }, 25);
  }
}

async function openDocuments(
  initialDocuments: object[] = [],
  useDefaultDocumentHandler = true,
) {
  sessionStorage.setItem("studypilot_access_token", "test-token");
  server.use(
    http.get(`${apiUrl}/auth/me`, () => HttpResponse.json(currentUser)),
    http.get(`${apiUrl}/courses/${courseId}`, () => HttpResponse.json(course)),
  );
  if (useDefaultDocumentHandler) {
    server.use(
      http.get(`${apiUrl}/courses/${courseId}/documents`, () =>
        HttpResponse.json(initialDocuments),
      ),
    );
  }
  await router.navigate(`/courses/${courseId}/documents`);
  return render(<App />);
}

describe("document management", () => {
  beforeEach(() => {
    vi.stubGlobal("XMLHttpRequest", MockXMLHttpRequest);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    MockXMLHttpRequest.response = readyDocument;
    MockXMLHttpRequest.status = 201;
    MockXMLHttpRequest.sentFile = undefined;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("uploads a valid PDF and displays progress", async () => {
    const user = userEvent.setup();
    await openDocuments();
    const input = await screen.findByLabelText("选择 PDF 文件");
    const file = new File(["pdf"], "notes.pdf", { type: "application/pdf" });
    await user.upload(input, file);

    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(await screen.findByText("network.pdf")).toBeInTheDocument();
    expect(MockXMLHttpRequest.sentFile?.name).toBe("notes.pdf");
  });

  it("rejects non-PDF and oversized files before upload", async () => {
    const user = userEvent.setup({ applyAccept: false });
    await openDocuments();
    const input = await screen.findByLabelText("选择 PDF 文件");
    await user.upload(
      input,
      new File(["text"], "notes.txt", { type: "text/plain" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("仅支持 PDF");
    expect(MockXMLHttpRequest.sentFile).toBeUndefined();

    const oversized = new File(["pdf"], "large.pdf", { type: "application/pdf" });
    Object.defineProperty(oversized, "size", { value: 20 * 1024 * 1024 + 1 });
    await user.upload(input, oversized);
    expect(screen.getByRole("alert")).toHaveTextContent("不能超过 20 MB");
    expect(MockXMLHttpRequest.sentFile).toBeUndefined();
  });

  it("polls pending documents and stops after ready", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let listCalls = 0;
    const processing = { ...readyDocument, id: "processing", status: "processing" };
    server.use(
      http.get(`${apiUrl}/courses/${courseId}/documents`, () => {
        listCalls += 1;
        return HttpResponse.json(listCalls === 1 ? [processing] : [readyDocument]);
      }),
    );
    await openDocuments([], false);
    expect(await screen.findByText("处理中")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByText("可用")).toBeInTheDocument();
    const callsAfterReady = listCalls;
    await vi.advanceTimersByTimeAsync(5000);
    expect(listCalls).toBe(callsAfterReady);
  });

  it("polls uploaded documents and stops after failure", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let listCalls = 0;
    const uploaded = { ...readyDocument, id: "uploaded", status: "uploaded" };
    const failed = {
      ...uploaded,
      status: "failed",
      failure_code: "parse_failed",
      failure_message: "PDF 解析失败。",
    };
    server.use(
      http.get(`${apiUrl}/courses/${courseId}/documents`, () => {
        listCalls += 1;
        return HttpResponse.json(listCalls === 1 ? [uploaded] : [failed]);
      }),
    );
    await openDocuments([], false);
    expect(await screen.findByText("等待处理")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByText("处理失败")).toBeInTheDocument();
    const callsAfterFailure = listCalls;
    await vi.advanceTimersByTimeAsync(5000);
    expect(listCalls).toBe(callsAfterFailure);
  });

  it("shows scanned-PDF failure and supports retry", async () => {
    let retryCalls = 0;
    const failed = {
      ...readyDocument,
      id: "failed-document",
      status: "failed",
      failure_code: "scanned_pdf",
      failure_message: "暂不支持扫描版 PDF。",
    };
    server.use(
      http.post(`${apiUrl}/documents/${failed.id}/retry`, () => {
        retryCalls += 1;
        return HttpResponse.json({ ...failed, status: "uploaded" });
      }),
    );
    const user = userEvent.setup();
    await openDocuments([failed]);
    expect(await screen.findByText("暂不支持扫描版 PDF。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(retryCalls).toBe(1));
  });

  it("requires confirmation and deletes a document", async () => {
    let deleteCalls = 0;
    server.use(
      http.delete(`${apiUrl}/documents/${readyDocument.id}`, () => {
        deleteCalls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    await openDocuments([readyDocument]);
    await user.click(await screen.findByRole("button", { name: "删除" }));
    expect(window.confirm).toHaveBeenCalledWith("确定删除“network.pdf”吗？");
    await waitFor(() => expect(deleteCalls).toBe(1));
  });

  it("redirects to courses when the course is missing", async () => {
    server.use(
      http.get(`${apiUrl}/courses/${courseId}`, () =>
        HttpResponse.json(
          { code: "course_not_found", message: "课程不存在。", request_id: "r1" },
          { status: 404 },
        ),
      ),
      http.get(`${apiUrl}/courses`, () => HttpResponse.json([])),
    );
    sessionStorage.setItem("studypilot_access_token", "test-token");
    server.use(http.get(`${apiUrl}/auth/me`, () => HttpResponse.json(currentUser)));
    await router.navigate(`/courses/${courseId}/documents`);
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "我的课程" }),
    ).toBeInTheDocument();
  });
});
