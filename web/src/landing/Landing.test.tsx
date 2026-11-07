import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Landing } from "./Landing";

describe("Landing", () => {
  it("leva para a ferramenta em /app pelos botões de entrada", () => {
    render(<Landing />);
    for (const id of ["lp-entrar", "lp-entrar-topo", "lp-entrar-final"]) {
      expect(screen.getByTestId(id)).toHaveAttribute("href", "/app");
    }
  });

  it("apresenta o FIO e o que ele faz", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/confere antes de pagar/);
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(5);
  });
});
