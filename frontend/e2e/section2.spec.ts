import { readFileSync } from 'node:fs'
import path from 'node:path'

import { expect, test } from './fixtures/test'
import {
  getHouseholdForUser,
  resetTestState,
  signIn as apiSignIn,
} from './helpers/admin'
import * as ui from './helpers/app'
import { env } from './helpers/env'
import { repoRoot } from './helpers/env'
import { allSeededUsers } from './helpers/users'

const fixtures = path.join(repoRoot, 'frontend', 'e2e', 'fixtures')
const png = (file: string) => readFileSync(path.join(fixtures, file))
const pdf = () => readFileSync(path.join(fixtures, 'bill.pdf'))

const JPEG_HEADER = Buffer.from([0xff, 0xd8, 0xff, 0xe0])

test.beforeEach(async ({ users }) => {
  await resetTestState(allSeededUsers(users))
})

async function setUpHousehold(page: Parameters<typeof ui.signIn>[0], users: Parameters<typeof allSeededUsers>[0]) {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Scan home ${Date.now()}`)
}

async function addFiles(
  page: Parameters<typeof ui.signIn>[0],
  files: { name: string; mimeType: string; buffer: Buffer }[],
) {
  await page.getByLabel('Add bill pages or a PDF').setInputFiles(files)
}

test('E2E-2.1 upload one image and read it', async ({ page, users }) => {
  await setUpHousehold(page, users)
  await ui.openScan(page)

  await addFiles(page, [{ name: 'bill.png', mimeType: 'image/png', buffer: png('bill-en.png') }])
  await expect(page.getByText('1 page')).toBeVisible()
  await page.getByRole('button', { name: 'Save bill' }).click()

  await page.waitForURL((url) => url.pathname.startsWith('/receipts/'))
  await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('heading', { name: /Demo Store/ })).toBeVisible()
  await expect(page.getByText(/1,234\.50/)).toBeVisible()
  await expect(page.getByAltText('Bill page 1')).toBeVisible()
})

test('E2E-2.2 remove and reorder pages before upload', async ({ page, users }) => {
  await setUpHousehold(page, users)
  await ui.openScan(page)

  await addFiles(page, [
    { name: 'one.png', mimeType: 'image/png', buffer: png('bill-en.png') },
    { name: 'two.png', mimeType: 'image/png', buffer: png('bill-hi.png') },
    { name: 'three.png', mimeType: 'image/png', buffer: png('bill-mr.png') },
  ])
  await expect(page.getByText('3 pages')).toBeVisible()

  await page.getByRole('button', { name: 'Remove page 2' }).click()
  await page.getByRole('button', { name: 'Move page 2 earlier' }).click()
  await expect(page.getByText('2 pages')).toBeVisible()

  await page.getByRole('button', { name: 'Save bill' }).click()
  await page.waitForURL((url) => url.pathname.startsWith('/receipts/'))
  await expect(page.getByAltText('Bill page 1')).toBeVisible()
  await expect(page.getByAltText('Bill page 2')).toBeVisible()
  await expect(page.getByAltText('Bill page 3')).toHaveCount(0)
})

test('E2E-2.3 upload a PDF', async ({ page, users }) => {
  await setUpHousehold(page, users)
  await ui.openScan(page)

  await addFiles(page, [
    { name: 'bill.pdf', mimeType: 'application/pdf', buffer: pdf() },
  ])
  await expect(page.getByText('bill.pdf')).toBeVisible()
  await expect(page.getByText(/MB .* PDF/)).toBeVisible()
  await page.getByRole('button', { name: 'Save bill' }).click()

  await page.waitForURL((url) => url.pathname.startsWith('/receipts/'))
  await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByLabel('Bill PDF')).toBeVisible()
})

test('E2E-2.4 rejects a text file, 11 pages and an oversized page', async ({ page, users }) => {
  await setUpHousehold(page, users)
  await ui.openScan(page)

  await addFiles(page, [
    {
      name: 'notes.txt',
      mimeType: 'text/plain',
      buffer: readFileSync(path.join(fixtures, 'notes.txt')),
    },
  ])
  await expect(page.getByRole('alert')).toContainText(/JPEG, PNG, WebP/i)

  const many = Array.from({ length: 11 }, (_, index) => ({
    name: `page-${index}.png`,
    mimeType: 'image/png',
    buffer: png('bill-en.png'),
  }))
  await addFiles(page, many)
  await expect(page.getByRole('alert')).toContainText(/at most 10 pages/i)

  const oversized = Buffer.concat([JPEG_HEADER, Buffer.alloc(11 * 1024 * 1024)])
  await addFiles(page, [{ name: 'huge.jpg', mimeType: 'image/jpeg', buffer: oversized }])
  await expect(page.getByRole('alert')).toContainText(/10 MB/i)
})

test('E2E-2.5 skip-AI upload and manual tag', async ({ page, users }) => {
  await setUpHousehold(page, users)
  await ui.openScan(page)

  await addFiles(page, [{ name: 'bill.png', mimeType: 'image/png', buffer: png('bill-en.png') }])
  await page.getByLabel('Skip AI for this bill').check()
  await page.getByRole('button', { name: 'Save bill' }).click()

  await page.waitForURL((url) => url.pathname.startsWith('/receipts/'))
  await expect(page.getByText('Saved without AI')).toBeVisible()
  await expect(page.getByText('No tags yet. Add one below.')).toBeVisible()

  await page.getByLabel('New tag').fill('Warranty')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByText('warranty')).toBeVisible()
  await expect(page.getByText('user', { exact: true })).toBeVisible()
})

test('E2E-2.6 forced failure then Retry succeeds', async ({ page, request, users }) => {
  await setUpHousehold(page, users)
  const household = await getHouseholdForUser(users.owner.id)
  if (!household) throw new Error('Owner has no household')

  const session = await apiSignIn(users.owner.email)
  const uploaded = await request.post(`${env.apiBaseUrl}/receipts`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
    multipart: {
      'files[]': {
        name: 'bill.png',
        mimeType: 'image/png',
        buffer: png('bill-en.png'),
      },
      skip_ai: 'false',
    },
  })
  expect(uploaded.status()).toBe(202)
  const { id } = (await uploaded.json()) as { id: string }

  const failed = await request.post(`${env.apiBaseUrl}/test/receipts/${id}/fail`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  })
  expect(failed.status()).toBe(200)

  await page.goto(`/receipts/${id}`)
  await expect(page.getByText('AI quota reached')).toBeVisible()
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 30_000 })
})

test('E2E-2.9 capture input is mobile-friendly', async ({ page, users }) => {
  await setUpHousehold(page, users)
  await ui.openScan(page)

  const camera = page.getByLabel('Take a photo of a bill')
  await expect(camera).toHaveAttribute('accept', 'image/*,application/pdf')
  await expect(camera).toHaveAttribute('capture', 'environment')
})
