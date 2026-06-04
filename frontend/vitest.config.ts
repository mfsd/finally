import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: {
    jsx: "automatic"
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    css: true
  },
  resolve: {
    alias: {
      "@": new URL("./", import.meta.url).pathname
    }
  }
});
