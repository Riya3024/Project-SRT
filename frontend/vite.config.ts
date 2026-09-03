import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Minimal Vite config (Rule 15: no unnecessary plugins). Dev server proxying to the
// backend, build optimization, etc. are added by the phase that needs them.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
  },
});
