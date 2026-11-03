import { readFileSync } from 'node:fs'
import path from 'node:path'

import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'

import { expect, test } from './fixtures/test'
import {
  addMembers,
  getHouseholdForUser,
  resetTestState,
  seedReceipt,
  signIn,
  type TestUser,
} from './helpers/admin'
import * as ui from './helpers/app'
import { env, repoRoot } from './helpers/env'
import { allSeededUsers } from './helpers/users'

const bill = () =>
  readFileSync(path.join(repoRoot, 'frontend', 'e2e', 'fixtures', 'bill-en.png'))

test.beforeEach(async ({ users }) => {
  await resetTestState(allSeededUsers(users))
})

async function setUp(page: Page, user: TestUser, name = 'Section 5 home') {
  await ui.signIn(page, user)
  await ui.createHousehold(page, `${name} ${Date.now()}`)
  return signIn(user.email)
}

async function seedOne(token: string) {
  return seedReceipt(token, {
    title: 'Original power',
    merchant: 'Adani Electricity',
    amount: 6000,
    bill_date: '2026-01-10',
    raw_text: 'electricity bill',
    tags: ['electricity'],
  })
}

test('E2E-5.1 edit fields, reload and search', async ({ page, users }) => {
  const session = await setUp(page, users.owner)
  const receipt = await seedOne(session.access_token)

  await page.goto(`/receipts/${receipt.id}`)
  await page.getByLabel('Title').fill('Edited power bill')
  await page.getByLabel('Merchant').fill('Edited Electric Co')
  await page.getByLabel('Amount').fill('7777.50')
  await page.getByLabel('Bill date').fill('2026-03-04')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByRole('button', { name: 'Save' })).toBeEnabled()

  await page.reload()
  await expect(page.getByLabel('Title')).toHaveValue('Edited power bill')
  await expect(page.getByLabel('Merchant')).toHaveValue('Edited Electric Co')
  await expect(page.getByLabel('Amount')).toHaveValue('7777.50')
  await expect(page.getByLabel('Bill date')).toHaveValue('2026-03-04')

  await page.getByRole('link', { name: 'Home' }).filter({ visible: true }).click()
  await page.getByLabel('Search bills').fill('Edited Electric')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('Edited power bill')

  await page.getByLabel('Search bills').fill('over 7000')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
})

test('E2E-5.2 delete a receipt and its detail', async ({ page, users }) => {
  const session = await setUp(page, users.owner)
  const receipt = await seedOne(session.access_token)

  page.on('dialog', (dialog) => dialog.accept())
  await page.goto(`/receipts/${receipt.id}`)
  await page.getByRole('button', { name: 'Delete' }).click()
  await expect(page).toHaveURL((url) => url.pathname === '/')
  await expect(page.getByText('No bills yet')).toBeVisible()

  const missing = await page.request.get(`${env.apiBaseUrl}/receipts/${receipt.id}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  })
  expect(missing.status()).toBe(404)

  await page.goto(`/receipts/${receipt.id}`)
  await expect(page.getByText('Receipt not found.')).toBeVisible()
})

test('E2E-5.3 rotate invite code and reject old code', async ({ page, request, users }) => {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Rotate home ${Date.now()}`)
  await ui.openHousehold(page)
  const oldCode = await ui.readInviteCode(page)

  const household = await getHouseholdForUser(users.owner.id)
  if (!household) throw new Error('Owner has no household')
  await addMembers(household.id, [users.member])

  await page.getByRole('button', { name: 'Rotate code' }).click()
  await expect
    .poll(async () => ui.readInviteCode(page), { timeout: 10_000 })
    .not.toBe(oldCode)
  const newCode = await ui.readInviteCode(page)

  const memberSession = await signIn(users.member.email)
  const forbidden = await request.post(`${env.apiBaseUrl}/households/rotate-invite`, {
    headers: { Authorization: `Bearer ${memberSession.access_token}` },
  })
  expect(forbidden.status()).toBe(403)
  expect((await forbidden.json()).error.code).toBe('owner_only')

  await ui.signOut(page)
  await ui.signIn(page, users.outsider)
  await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()

  await page.getByLabel('Invite code').fill(oldCode)
  await page.getByRole('button', { name: 'Join household' }).click()
  await expect(page.getByRole('alert')).toContainText(/not valid/i)
  await expect(page).toHaveURL((url) => url.pathname === '/onboarding')

  await page.getByLabel('Invite code').fill(newCode)
  await page.getByRole('button', { name: 'Join household' }).click()
  await expect(page).toHaveURL((url) => url.pathname === '/')
})

test('E2E-5.5 manifest, icons and service worker', async ({ page, request }) => {
  const manifest = await request.get(`${env.appUrl}/manifest.webmanifest`)
  expect(manifest.status()).toBe(200)
  const body = (await manifest.json()) as {
    name?: string
    icons?: Array<{ src: string }>
  }
  expect(body.name).toBe('BillBox')
  expect(body.icons?.length ?? 0).toBeGreaterThanOrEqual(3)
  for (const icon of body.icons ?? []) {
    const response = await request.get(`${env.appUrl}${icon.src}`)
    expect(response.status(), icon.src).toBe(200)
  }

  await page.goto('/signin')
  await expect
    .poll(
      () =>
        page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length),
      { timeout: 15_000 },
    )
    .toBeGreaterThan(0)
})

test('E2E-5.6 mobile has no horizontal scroll and usable nav', async ({ page, users }) => {
  const width = page.viewportSize()?.width ?? 0
  test.skip(width > 768, 'Mobile-only layout check')

  await setUp(page, users.owner)
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
  await expect(
    page.getByRole('navigation', { name: 'Primary' }).filter({ visible: true }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: 'Scan' }).filter({ visible: true })).toBeVisible()
})

test('E2E-5.7 slow API shows the waking banner', async ({ page, users }) => {
  await setUp(page, users.owner)
  await page.route('**/receipts?**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2500))
    await route.continue()
  })

  await page.reload()
  await expect(page.getByRole('status')).toContainText('Waking up the server')
  await expect(page.getByRole('status')).toHaveCount(0, { timeout: 15_000 })
})

test('E2E-5.8 full journey with two accounts', async ({ page, users }) => {
  page.on('dialog', (dialog) => dialog.accept())

  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Journey home ${Date.now()}`)
  await ui.openHousehold(page)
  const code = await ui.readInviteCode(page)

  await ui.signOut(page)
  await ui.signIn(page, users.member)
  await ui.joinHousehold(page, code)

  await page.getByRole('link', { name: 'Scan' }).filter({ visible: true }).click()
  await page
    .getByLabel('Add bill pages or a PDF')
    .setInputFiles([{ name: 'bill.png', mimeType: 'image/png', buffer: bill() }])
  await page.getByRole('button', { name: 'Save bill' }).click()
  await page.waitForURL((url) => url.pathname.startsWith('/receipts/'))
  await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 30_000 })

  await page.getByLabel('New tag').fill('Warranty')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByText('Warranty')).toBeVisible()

  await page.getByRole('link', { name: 'Home' }).filter({ visible: true }).click()
  await page.getByLabel('Search bills').fill('Demo Store')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)

  await ui.signOut(page)
  await ui.signIn(page, users.owner)
  await page.getByLabel('Search bills').fill('Demo Store')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)

  await page.getByTestId('receipt-card').click()
  await expect(page.getByRole('heading', { name: /Demo Store/ })).toBeVisible()
  await page.getByRole('button', { name: 'Delete' }).click()
  await expect(page).toHaveURL((url) => url.pathname === '/')
  await expect(page.getByText('No bills yet')).toBeVisible()
})

test('E2E-5.9 accessibility smoke', async ({ page, users }) => {
  const session = await setUp(page, users.owner)
  await seedOne(session.access_token)
  await page.reload()

  for (const route of ['/', '/scan', '/household']) {
    await page.goto(route)
    const results = await new AxeBuilder({ page }).analyze()
    const critical = results.violations.filter((violation) => violation.impact === 'critical')
    expect(critical, `${route}: ${critical.map((item) => item.id).join(', ')}`).toEqual([])
  }

  await page.goto('/scan')
  await expect(page.getByLabel('Add bill pages or a PDF')).toBeVisible()
})
