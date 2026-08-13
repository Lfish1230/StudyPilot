import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "../../App";
import { server } from "../../test/server";

const apiUrl = "http://localhost:8000";
const currentUser = {
  id: "user-1",
  email: "student@example.com",
  created_at: "2026-08-13T00:00:00Z",
};

describe("authentication", () => {
  it("redirects unauthenticated course visits to login", async () => {
    window.history.replaceState({}, "", "/courses");
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "登录继续学习" }),
    ).toBeInTheDocument();
  });

  it("stores a successful login token and opens courses", async () => {
    server.use(
      http.post(`${apiUrl}/auth/login`, () =>
        HttpResponse.json({ access_token: "test-token", token_type: "bearer" }),
      ),
      http.get(`${apiUrl}/auth/me`, ({ request }) => {
        expect(request.headers.get("Authorization")).toBe("Bearer test-token");
        return HttpResponse.json(currentUser);
      }),
      http.get(`${apiUrl}/courses`, () => HttpResponse.json([])),
    );
    window.history.replaceState({}, "", "/login");
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("邮箱"), currentUser.email);
    await user.type(screen.getByLabelText("密码"), "correct-horse-42");
    await user.click(screen.getByRole("button", { name: "登录" }));

    expect(
      await screen.findByRole("heading", { name: "我的课程" }),
    ).toBeInTheDocument();
    expect(sessionStorage.getItem("studypilot_access_token")).toBe("test-token");
  });

  it("restores a token through me and clears auth on any 401", async () => {
    sessionStorage.setItem("studypilot_access_token", "expired-token");
    server.use(
      http.get(`${apiUrl}/auth/me`, () => HttpResponse.json(currentUser)),
      http.get(`${apiUrl}/courses`, () =>
        HttpResponse.json(
          { code: "invalid_token", message: "登录状态无效。", request_id: "r1" },
          { status: 401 },
        ),
      ),
    );
    window.history.replaceState({}, "", "/courses");
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "登录继续学习" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(sessionStorage.getItem("studypilot_access_token")).toBeNull(),
    );
  });
});
