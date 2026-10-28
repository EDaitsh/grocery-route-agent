import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// בפיתוח (npm run dev) הבקשות ל-/api מועברות לשרת ה-FastAPI שרץ ב-python run_web.py
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
