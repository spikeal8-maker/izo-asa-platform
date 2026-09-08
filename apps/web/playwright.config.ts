import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', fullyParallel: true, forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0, workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: { command: 'npm run preview', url: 'http://127.0.0.1:4173', reuseExistingServer: !process.env.CI },
  projects: [
    { name: 'phone-small', use: { viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true } },
    { name: 'phone', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
    { name: 'tablet', use: { viewport: { width: 768, height: 1024 }, hasTouch: true } },
    { name: 'tablet-landscape', use: { viewport: { width: 1024, height: 768 }, hasTouch: true } },
    { name: 'laptop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'desktop', use: { viewport: { width: 1920, height: 1080 } } },
  ],
})
