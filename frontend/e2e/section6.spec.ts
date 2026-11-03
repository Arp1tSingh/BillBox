import { readFileSync } from 'node:fs'
import path from 'node:path'

import { expect, test } from './fixtures/test'
import { resetTestState } from './helpers/admin'
import * as ui from './helpers/app'
import { repoRoot } from './helpers/env'
import { allSeededUsers } from './helpers/users'

const bill = () =>
  readFileSync(path.join(repoRoot, 'frontend', 'e2e', 'fixtures', 'bill-en.png'))

test.beforeEach(async ({ users }) => {
  await resetTestState(allSeededUsers(users))
})

test('E2E-6.1 export downloads a ZIP', async ({ page, users }) => {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Export home ${Date.now()}`)
  await ui.openScan(page)
  await page
    .getByLabel('Add bill pages or a PDF')
    .setInputFiles([{ name: 'bill.png', mimeType: 'image/png', buffer: bill() }])
  await page.getByRole('button', { name: 'Save bill' }).click()
  await page.waitForURL((url) => url.pathname.startsWith('/receipts/'))

  await ui.openHousehold(page)
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export ZIP' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^billbox-export-.*\.zip$/)
  const filePath = await download.path()
  expect(filePath).toBeTruthy()
  const bytes = readFileSync(filePath as string)
  expect(bytes.subarray(0, 2).toString()).toBe('PK')
})

test.describe('E2E-6.2 offline capture', () => {
  // Keep the request flow deterministic: the app shell is already loaded, and
  // the queue must be exercised rather than the service worker cache.
  test.use({ serviceWorkers: 'block' })

  test('saves a bill offline and uploads it on reconnect', async ({ page, context, users }) => {
    await ui.signIn(page, users.owner)
    await ui.createHousehold(page, `Offline home ${Date.now()}`)
    await ui.openScan(page)

    await context.setOffline(true)
    await page
      .getByLabel('Add bill pages or a PDF')
      .setInputFiles([{ name: 'offline.png', mimeType: 'image/png', buffer: bill() }])
    await page.getByRole('button', { name: 'Save bill' }).click()

    await expect(page.getByText(/^Saved offline\./)).toBeVisible()
    await expect(page.getByTestId('upload-queue-banner')).toContainText('1 bill saved offline')

    await context.setOffline(false)
    await expect(page.getByTestId('upload-queue-banner')).toHaveCount(0, { timeout: 30_000 })

    await ui.openHome(page)
    await expect(page.getByTestId('receipt-card')).toHaveCount(1)
    await expect(page.getByTestId('receipt-card')).toContainText('Demo Store')
  })
})
