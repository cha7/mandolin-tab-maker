import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    // Same as jsconfig.json's "@/*" -> "./src/*".
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  test: {
    environment: "node",
    // The app and scripts; the Python engine's tests are pytest (tests/).
    include: ["src/**/*.test.js", "scripts/**/*.test.js"],
  },
});
