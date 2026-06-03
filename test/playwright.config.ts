import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './specs',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:8000',
    headless: true,
  },
  reporter: [['list'], ['json', { outputFile: 'test-results.json' }]],
})
