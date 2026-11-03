import type { Page } from '@playwright/test'

import { expect, test } from './fixtures/test'
import { resetTestState, seedReceipt, signIn } from './helpers/admin'
import * as ui from './helpers/app'
import { allSeededUsers, type SeedUsers } from './helpers/users'

test.beforeEach(async ({ users }) => {
  await resetTestState(allSeededUsers(users))
})

function isoDate(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(
    value.getDate(),
  ).padStart(2, '0')}`
}

function dayInMonth(offset: number, day = 2): string {
  const now = new Date()
  return isoDate(new Date(now.getFullYear(), now.getMonth() + offset, day))
}

async function setUp(page: Page, users: SeedUsers) {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Search home ${Date.now()}`)
  const session = await signIn(users.owner.email)
  const seed = (input: Parameters<typeof seedReceipt>[1]) =>
    seedReceipt(session.access_token, input)

  await seed({
    title: 'December power',
    merchant: 'Adani Electricity',
    amount: 6000,
    bill_date: '2025-12-10',
    raw_text: 'electricity bill MSEDCL',
    tags: ['electricity'],
  })
  await seed({
    title: 'Water bill',
    merchant: 'Delhi Jal Board',
    amount: 900,
    bill_date: '2026-01-15',
    raw_text: 'पाणी बिल water bill',
    tags: ['water'],
  })
  await seed({
    title: 'Monthly kirana',
    merchant: 'Kirana Store',
    amount: 1500,
    bill_date: '2026-02-05',
    raw_text: 'grocery bill',
    tags: ['groceries'],
  })
  await seed({
    title: 'Power and kirana',
    merchant: 'Adani Electricity',
    amount: 2500,
    bill_date: '2026-02-10',
    raw_text: 'electricity bill grocery',
    tags: ['electricity', 'groceries'],
  })
  await seed({
    title: 'Last month power',
    merchant: 'Adani Electricity',
    amount: 2000,
    bill_date: dayInMonth(-1),
    raw_text: 'electricity bill',
    tags: ['electricity'],
  })
  await seed({
    title: 'This month power',
    merchant: 'Adani Electricity',
    amount: 3000,
    bill_date: dayInMonth(0),
    raw_text: 'electricity bill',
    tags: ['electricity'],
  })

  await page.reload()
  await expect(page.getByTestId('receipt-card')).toHaveCount(6)
}

async function search(page: Page, term: string) {
  await page.getByLabel('Search bills').fill(term)
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page).toHaveURL((url) => url.searchParams.get('q') === term)
}

test('E2E-4.1 search electricity bill', async ({ page, users }) => {
  await setUp(page, users)
  await search(page, 'electricity bill')

  const cards = page.getByTestId('receipt-card')
  await expect(cards).toHaveCount(4)
  await expect(page.getByTestId('receipt-list')).toContainText('December power')
  await expect(page.getByTestId('receipt-list')).toContainText('Power and kirana')
  await expect(page.getByTestId('receipt-list')).not.toContainText('Water bill')
  await expect(page.getByTestId('receipt-list')).not.toContainText('Monthly kirana')
})

test('E2E-4.2 search Hindi and Marathi tags', async ({ page, users }) => {
  await setUp(page, users)

  await search(page, 'बिजली')
  await expect(page.getByTestId('receipt-card')).toHaveCount(4)
  await expect(page.getByTestId('receipt-list')).toContainText('December power')

  await search(page, 'पाणी')
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('Water bill')
})

test('E2E-4.3 search amount phrases', async ({ page, users }) => {
  await setUp(page, users)

  await search(page, 'over 5000')
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('December power')

  await search(page, 'under 1000')
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('Water bill')

  await search(page, 'between 1000 and 5000')
  await expect(page.getByTestId('receipt-card')).toHaveCount(4)
  await expect(page.getByTestId('receipt-list')).not.toContainText('December power')
  await expect(page.getByTestId('receipt-list')).not.toContainText('Water bill')
})

test('E2E-4.4 search last month and a year', async ({ page, users }) => {
  await setUp(page, users)

  await search(page, 'last month')
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('Last month power')

  await search(page, '2025')
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('December power')
})

test('E2E-4.5 merchant trigram search', async ({ page, users }) => {
  await setUp(page, users)
  await search(page, 'Adani Elec')

  await expect(page.getByTestId('receipt-card')).toHaveCount(4)
  await expect(page.getByTestId('receipt-list')).toContainText('December power')
})

test('E2E-4.6 tag chips use AND then clear', async ({ page, users }) => {
  await setUp(page, users)

  await page.getByRole('button', { name: /^Electricity/ }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(4)

  await page.getByRole('button', { name: /^Groceries/ }).click()
  await expect(page).toHaveURL((url) => url.searchParams.getAll('tag').length === 2)
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('Power and kirana')

  await page.getByRole('button', { name: 'Clear', exact: true }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(6)
})

test('E2E-4.7 sort and paginate 25 receipts', async ({ page, users }) => {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Paging home ${Date.now()}`)
  const session = await signIn(users.owner.email)

  for (let index = 1; index <= 25; index += 1) {
    await seedReceipt(session.access_token, {
      title: `Pagination ${index}`,
      merchant: 'Paging Store',
      amount: index * 100,
      bill_date: `2026-01-${String(index).padStart(2, '0')}`,
      raw_text: 'pagination receipt',
    })
  }

  await page.reload()
  await expect(page.getByText('Page 1 of 2')).toBeVisible()
  await expect(page.getByTestId('receipt-card')).toHaveCount(20)

  await page.getByLabel('Sort').selectOption('amount')
  await expect(page.getByTestId('receipt-card').first()).toContainText('Pagination 25')

  await page.getByRole('button', { name: 'Next' }).click()
  await expect(page.getByText('Page 2 of 2')).toBeVisible()
  await expect(page.getByTestId('receipt-card')).toHaveCount(5)
  await expect(page.getByTestId('receipt-card').first()).toContainText('Pagination 5')
  await expect(page.getByTestId('receipt-list')).not.toContainText('Pagination 25')

  await page.getByRole('button', { name: 'Previous' }).click()
  await expect(page.getByText('Page 1 of 2')).toBeVisible()
  await expect(page.getByTestId('receipt-card')).toHaveCount(20)
})

test('E2E-4.8 empty result and URL state', async ({ page, users }) => {
  await setUp(page, users)

  await search(page, 'electricity')
  await expect(page.getByTestId('receipt-card')).toHaveCount(4)

  await page.reload()
  await expect(page.getByLabel('Search bills')).toHaveValue('electricity')
  await expect(page.getByTestId('receipt-card')).toHaveCount(4)

  await page.getByRole('button', { name: /^Groceries/ }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await page.goBack()
  await expect(page.getByLabel('Search bills')).toHaveValue('electricity')
  await expect(page.getByTestId('receipt-card')).toHaveCount(4)

  await search(page, 'zzzz-nothing')
  await expect(page.getByRole('heading', { name: 'No bills match that search' })).toBeVisible()
  await page.getByRole('button', { name: 'Clear search' }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(6)
})

test('E2E-4.10 outsider cannot search another household', async ({ page, users }) => {
  await setUp(page, users)
  await ui.signOut(page)
  await ui.signIn(page, users.outsider)
  await ui.createHousehold(page, `Outsider home ${Date.now()}`)

  await search(page, 'electricity')
  await expect(page.getByRole('heading', { name: 'No bills match that search' })).toBeVisible()
  await expect(page.getByTestId('receipt-card')).toHaveCount(0)
})

test('E2E-4.11 add, filter, remove and re-add a custom tag', async ({ page, users }) => {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Custom tag home ${Date.now()}`)
  const session = await signIn(users.owner.email)
  const receipt = await seedReceipt(session.access_token, {
    title: 'Warranty mixer',
    merchant: 'Mixer Store',
    amount: 3200,
    bill_date: '2026-02-01',
    raw_text: 'mixer grinder bill',
    tags: ['groceries'],
  })

  await page.goto(`/receipts/${receipt.id}`)
  await page.getByLabel('New tag').fill('Warranty')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByText('Warranty')).toBeVisible()

  await ui.openHome(page)
  await page.getByRole('button', { name: /^Warranty/ }).click()
  await expect(page.getByTestId('receipt-card')).toHaveCount(1)
  await expect(page.getByTestId('receipt-list')).toContainText('Warranty mixer')

  await page.getByTestId('receipt-card').click()
  await page.getByRole('button', { name: 'Remove Warranty tag' }).click()
  await expect(page.getByText('Warranty')).toHaveCount(0)

  await ui.openHome(page)
  await expect(page.getByRole('button', { name: /^Warranty/ })).toHaveCount(0)

  await page.getByTestId('receipt-card').click()
  await page.getByLabel('New tag').fill('Warranty')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await ui.openHome(page)
  await expect(page.getByRole('button', { name: /^Warranty/ })).toBeVisible()
})
