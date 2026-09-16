import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Ensure the DOM is reset between tests so components don't leak into each
// other (React Testing Library does not auto-clean with Vitest globals).
afterEach(() => {
  cleanup();
});
