import { describe, expect, it, afterEach } from "vitest";
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { RouterProvider, useRouter, Link, matchRoute } from "./Router";

afterEach(() => {
  cleanup();
});

function DummyPage() {
  const { currentPath, navigate } = useRouter();
  return (
    <div>
      <span data-testid="current-path">{currentPath}</span>
      <Link to="/workflows" activeClassName="is-active">
        Workflows Link
      </Link>
      <button onClick={() => navigate("/runs/run-123")}>Go to run 123</button>
    </div>
  );
}

describe("matchRoute", () => {
  it("matches exact paths", () => {
    expect(matchRoute("/runs", "/runs")).toEqual({ matched: true, params: {} });
    expect(matchRoute("/workflows", "/runs")).toEqual({ matched: false, params: {} });
  });

  it("extracts path parameters", () => {
    const res = matchRoute("/runs/:id", "/runs/run-abc");
    expect(res).toEqual({ matched: true, params: { id: "run-abc" } });
  });

  it("matches catch-all paths with :path*", () => {
    const res = matchRoute("/workflows/:path*", "/workflows/sub/my_wf.yaml");
    expect(res).toEqual({
      matched: true,
      params: { path: "sub/my_wf.yaml" },
    });
  });
});

describe("Router and Link component", () => {
  it("renders with default route /workflows", () => {
    window.location.hash = "";
    render(
      <RouterProvider>
        <DummyPage />
      </RouterProvider>,
    );
    expect(screen.getByTestId("current-path").textContent).toBe("/workflows");
  });

  it("updates path on navigation button click", () => {
    render(
      <RouterProvider>
        <DummyPage />
      </RouterProvider>,
    );
    const btn = screen.getByText("Go to run 123");
    fireEvent.click(btn);
    expect(window.location.hash).toBe("#/runs/run-123");
  });

  it("handles Link click and active classes", () => {
    render(
      <RouterProvider>
        <DummyPage />
      </RouterProvider>,
    );
    const link = screen.getByText("Workflows Link");
    fireEvent.click(link);
    expect(window.location.hash).toBe("#/workflows");
  });

  it("updates path when hash changes externally", () => {
    render(
      <RouterProvider>
        <DummyPage />
      </RouterProvider>,
    );
    act(() => {
      window.location.hash = "#/workflows";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(screen.getByTestId("current-path").textContent).toBe("/workflows");
  });
});
