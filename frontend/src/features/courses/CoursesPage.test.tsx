import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import { server } from "../../test/server";

const apiUrl = "http://localhost:8000";
const currentUser = {
  id: "user-1",
  email: "student@example.com",
  created_at: "2026-08-13T00:00:00Z",
};
const oldCourse = {
  id: "course-old",
  name: "数据结构",
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
};
const newCourse = {
  id: "course-new",
  name: "计算机网络",
  created_at: "2026-08-12T00:00:00Z",
  updated_at: "2026-08-12T00:00:00Z",
};

function openCourses() {
  sessionStorage.setItem("studypilot_access_token", "test-token");
  window.history.replaceState({}, "", "/courses");
  server.use(http.get(`${apiUrl}/auth/me`, () => HttpResponse.json(currentUser)));
  return render(<App />);
}

describe("course list", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders courses newest first", async () => {
    server.use(
      http.get(`${apiUrl}/courses`, () =>
        HttpResponse.json([oldCourse, newCourse]),
      ),
    );
    openCourses();
    const headings = await screen.findAllByRole("heading", { level: 2 });
    expect(headings.map((heading) => heading.textContent)).toEqual([
      "计算机网络",
      "数据结构",
    ]);
  });

  it("rejects a blank name before making a request", async () => {
    let createCalls = 0;
    server.use(
      http.get(`${apiUrl}/courses`, () => HttpResponse.json([])),
      http.post(`${apiUrl}/courses`, () => {
        createCalls += 1;
        return HttpResponse.json(newCourse, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    openCourses();
    await screen.findByRole("heading", { name: "我的课程" });
    await user.type(screen.getByLabelText("新课程名称"), "   ");
    await user.click(screen.getByRole("button", { name: "创建课程" }));
    expect(screen.getByRole("alert")).toHaveTextContent("课程名称不能为空");
    expect(createCalls).toBe(0);
  });

  it("requires confirmation before deleting a course", async () => {
    let deleteCalls = 0;
    server.use(
      http.get(`${apiUrl}/courses`, () => HttpResponse.json([newCourse])),
      http.delete(`${apiUrl}/courses/${newCourse.id}`, () => {
        deleteCalls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    openCourses();
    await user.click(await screen.findByRole("button", { name: "删除" }));
    expect(window.confirm).toHaveBeenCalledWith(
      "确定删除“计算机网络”吗？相关资料也会被删除。",
    );
    expect(deleteCalls).toBe(0);

    vi.mocked(window.confirm).mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(deleteCalls).toBe(1));
  });
});
