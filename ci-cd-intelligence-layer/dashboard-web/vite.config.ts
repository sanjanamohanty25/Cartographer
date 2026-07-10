import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Gateway CORS is open, so the app talks to VITE_API_URL directly (default :8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
