import "@testing-library/jest-dom";
import React from "react";
import { vi } from "vitest";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) =>
    React.createElement("a", { href, ...rest }, children)
}));
