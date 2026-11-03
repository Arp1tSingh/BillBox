import { defineConfig, devices } from '@playwright/test'

import { env } from './e2e/helpers/env'

const cleanEnv = Object.fromEntries(
  Object.entries(process.env).filter((entry): entry is [string, string] => typeof entry[1] === 'string'),
)

const appUrl = new URL(env.appUrl)
const appPort = appUrl.port || '5173'

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI
    ? [['github'], ['html', { open: 'never' }]]
    : [['list'], ['html', { open: 'never' }]],
  outputDir: 'test-results',
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: env.appUrl,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
    { name: 'mobile-safari', use: { ...devices['iPhone 13'] } },
  ],
  webServer: [
    {
      command: 'node e2e/scripts/start-backend.mjs',
      url: `${env.apiBaseUrl}/health`,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        ...cleanEnv,
        ENVIRONMENT: 'test',
        GEMINI_MOCK: '1',
        SUPABASE_URL: env.supabaseUrl,
        SUPABASE_ANON_KEY: env.anonKey,
        SUPABASE_SERVICE_ROLE_KEY: env.serviceRoleKey,
        CORS_ORIGINS: `${env.appUrl},http://localhost:5173`,
      },
    },
    {
      command: `npm run dev -- --host ${appUrl.hostname} --port ${appPort}`,
      url: env.appUrl,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        ...cleanEnv,
        VITE_SUPABASE_URL: env.supabaseUrl,
        VITE_SUPABASE_ANON_KEY: env.anonKey,
        VITE_API_BASE_URL: env.apiBaseUrl,
      },
    },
  ],
})
