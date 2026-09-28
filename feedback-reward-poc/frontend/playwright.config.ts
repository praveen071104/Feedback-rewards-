import { defineConfig } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

process.env.FEEDBACK_E2E_DATABASE ??= `feedback_reward_e2e_${randomUUID().replaceAll('-', '')}`
const python = fileURLToPath(new URL(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python', import.meta.url))
const tickets = path.join(tmpdir(), `${process.env.FEEDBACK_E2E_DATABASE}.sqlite3`)
process.env.FEEDBACK_E2E_TICKETS = tickets

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  webServer: [
    {
      command: `"${python}" -m uvicorn main:app --app-dir ../backend --host 127.0.0.1 --port 8001`,
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: false,
      env: { MONGODB_URI: 'mongodb://127.0.0.1:27017/', MONGODB_DATABASE: process.env.FEEDBACK_E2E_DATABASE, FEEDBACK_TICKETS_DB: tickets },
    },
    {
      command: 'npm run dev -- --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: false,
      env: { FEEDBACK_API_URL: 'http://127.0.0.1:8001' },
    },
  ],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    channel: process.env.PLAYWRIGHT_CHANNEL || (process.platform === 'win32' ? 'msedge' : 'chromium'),
    viewport: { width: 1440, height: 1000 },
  },
})