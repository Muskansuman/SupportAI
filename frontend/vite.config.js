import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Vite's dev-server rejects requests with an unrecognized Host header
    // by default (DNS-rebinding protection). Needed here because the
    // Cloudflare quick-tunnel URL isn't localhost — fine for a temporary
    // public demo, not something to leave open on a real deployment.
    allowedHosts: true,
  },
})
