import { http, HttpResponse } from "msw";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";
import { server } from "./test/server";

describe("App", () => {
  it("renders the StudyPilot login shell", async () => {
    server.use(
      http.get("http://localhost:8000/auth/me", () =>
        HttpResponse.json({}, { status: 401 }),
      ),
    );
    window.history.replaceState({}, "", "/login");
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "登录继续学习" }),
    ).toBeInTheDocument();
  });
});
