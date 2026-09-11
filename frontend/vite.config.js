import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite is the development server and the build tool. It serves the app while
// you work, reloading the browser the moment you save a file.
export default defineConfig({
  plugins: [
    react(),
    // Tailwind v4 plugs straight into Vite. No separate config file needed:
    // the design tokens live in src/index.css instead.
    tailwindcss(),
  ],
  server: {
    port: 5173,
    // Anything the app requests at /api is forwarded to the FastAPI server.
    // Without this the browser would block the call, because a page served
    // from port 5173 is not allowed to call port 8000 by default.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
