import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { EmptyState } from "./empty-state";

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="비어있음" description="아직 데이터가 없습니다" />);

    expect(screen.getByText("비어있음")).toBeInTheDocument();
    expect(screen.getByText("아직 데이터가 없습니다")).toBeInTheDocument();
  });

  it("renders optional action slot", () => {
    render(
      <EmptyState title="without data" action={<button type="button">Retry</button>} />,
    );

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
