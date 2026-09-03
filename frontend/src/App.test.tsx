import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

// Phase 2 smoke test only: proves the React + TypeScript + Vitest toolchain
// actually renders the placeholder scaffold. Does not test any dashboard
// feature, because none exist yet (Rule 13: "test only what actually exists").
describe("App (Phase 2 scaffold)", () => {
  it("renders the environment-ready placeholder", () => {
    render(<App />);
    expect(screen.getByText("Project SRT")).toBeInTheDocument();
    expect(screen.getByText(/development environment ready/i)).toBeInTheDocument();
  });
});
