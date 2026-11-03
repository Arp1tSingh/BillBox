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
  await page.getByRole('link', { name: 'Scan' }).filter({ visible: true }).click()
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
