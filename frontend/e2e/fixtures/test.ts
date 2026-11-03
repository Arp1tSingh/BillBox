import { test as base, expect } from '@playwright/test'

import { loadUsers, type SeedUsers } from '../helpers/users'

const IGNORED_CONSOLE_PATTERNS = [
  /favicon\.ico/i,
  /\[vite\]/i,
  /Download the React DevTools/i,
  // The browser logs a generic message for every failed response. Expected 4xx
  // responses are part of several flows (no household yet, deleted receipt,
  // full household); unexpected server faults are still caught by the 5xx
  // response listener below.
  /Failed to load resource: the server responded with a status of 4\d\d/i,
  // Offline tests deliberately drop the network; the app queues the upload.
  // Safari reports the same failure with a sentence rather than a net:: code.
  /Failed to load resource: .*(offline|ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED)/i,
]

interface BillBoxFixtures {
  consoleErrors: string[]
  users: SeedUsers
}

export const test = base.extend<BillBoxFixtures>({
  users: async ({}, use) => {
    await use(loadUsers())
  },

  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []

      page.on('console', (message) => {
        if (message.type() !== 'error') return
        const text = message.text()
        if (IGNORED_CONSOLE_PATTERNS.some((pattern) => pattern.test(text))) return
        errors.push(text)
      })
      page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
      page.on('response', (response) => {
        if (response.status() >= 500) {
          errors.push(`5xx ${response.status()} ${response.url()}`)
        }
      })

      await use(errors)

      expect(errors, 'Console errors or 5xx responses during the test').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }
