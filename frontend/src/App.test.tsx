import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("renders the StudyPilot shell", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "StudyPilot" }),
    ).toBeInTheDocument();
  });
});

