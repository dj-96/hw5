import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The desk runs at http://localhost:5173 and calls the FastAPI backend
// (see src/api.ts; override with VITE_API_URL in frontend/.env.local).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: false },
})
