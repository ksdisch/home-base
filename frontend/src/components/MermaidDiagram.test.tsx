import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MermaidDiagram } from "./MermaidDiagram";

// jsdom can't lay out real SVG, so the mermaid module is mocked: these tests pin the component's
// contract (lazy import → initialize once → render → inject SVG; source fallback on failure),
// not mermaid's own output.
const initialize = vi.fn();
const renderDiagram = vi.fn();
vi.mock("mermaid", () => ({
  default: {
    initialize: (...a: unknown[]) => initialize(...a),
    render: (id: string, src: string) => renderDiagram(id, src),
  },
}));

beforeEach(() => {
  initialize.mockReset();
  renderDiagram.mockReset();
});

describe("MermaidDiagram", () => {
  it("renders the diagram SVG with strict security", async () => {
    renderDiagram.mockResolvedValue({ svg: '<svg data-testid="diagram-svg"></svg>' });
    render(<MermaidDiagram source={"flowchart LR\nA-->B"} />);

    expect(await screen.findByRole("img", { name: /course diagram/i })).toBeInTheDocument();
    expect(renderDiagram).toHaveBeenCalledWith(expect.any(String), "flowchart LR\nA-->B");
    // initialize ran (once per app, not per render) and demanded the strict sandbox.
    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({ securityLevel: "strict", startOnLoad: false }),
    );
  });

  it("falls back to the labeled source block when rendering fails", async () => {
    renderDiagram.mockRejectedValue(new Error("Parse error"));
    render(<MermaidDiagram source="not a diagram" />);

    await waitFor(() =>
      expect(screen.getByText(/showing the Mermaid source/i)).toBeInTheDocument(),
    );
    expect(screen.getByText("not a diagram")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
