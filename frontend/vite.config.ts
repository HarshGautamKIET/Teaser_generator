import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Oripio design system lives at <repo>/design-system; `@ds` points at it so
// the token layer is consumed from source rather than copied into the app.
const designSystem = fileURLToPath(new URL("../design-system", import.meta.url));

// Env vars live in the repository-root .env alongside the backend settings.
export default defineConfig({
  plugins: [react()],
  envDir: "..",
  resolve: { alias: { "@ds": designSystem } },
  server: { port: 5173, fs: { allow: [".."] } },
});
