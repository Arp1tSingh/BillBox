import { test as base, expect } from '@playwright/test'

import { loadUsers, type SeedUsers } from '../helpers/users'

const IGNORED_CONSOLE_PATTERNS = [
  /favicon\.ico/i,
  /\[vite\]/i,
  /Download the React DevTools/i,
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
