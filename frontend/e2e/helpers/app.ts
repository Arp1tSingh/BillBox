import { expect, type Page } from '@playwright/test'

import { TEST_PASSWORD, type TestUser } from './admin'

export async function signIn(page: Page, user: TestUser): Promise<void> {
  await page.goto('/signin')
  await page.getByLabel('Email').fill(user.email)
  await page.getByLabel('Password').fill(user.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL((url) => url.pathname === '/' || url.pathname === '/onboarding')
}

export async function signUp(page: Page, email: string, password = TEST_PASSWORD): Promise<void> {
  await page.goto('/signin')
  await page.getByRole('button', { name: /Create an account/ }).click()
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await page.waitForURL((url) => url.pathname === '/onboarding')
}

export async function createHousehold(page: Page, name: string): Promise<void> {
  await page.getByLabel('Household name').fill(name)
  await page.getByRole('button', { name: 'Create household' }).click()
  await expect(page).toHaveURL((url) => url.pathname === '/')
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()
}

export async function joinHousehold(page: Page, code: string): Promise<void> {
  await page.getByLabel('Invite code').fill(code)
  await page.getByRole('button', { name: 'Join household' }).click()
  await expect(page).toHaveURL((url) => url.pathname === '/')
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()
}

/**
 * The desktop header and the mobile tab bar both render the primary nav, but
 * only one is in the accessibility tree at a given viewport. Scope to the nav
 * and match the label exactly so headings or CTA copy such as "Back to Home"
 * and "Scan a bill" never collide with a nav link.
 */
export function navLink(page: Page, name: 'Home' | 'Scan' | 'Household') {
  return page
    .getByRole('navigation', { name: 'Primary' })
    .getByRole('link', { name, exact: true })
}

export async function openHome(page: Page): Promise<void> {
  await navLink(page, 'Home').click()
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()
}

export async function openScan(page: Page): Promise<void> {
  await navLink(page, 'Scan').click()
  await expect(page.getByRole('heading', { name: 'Scan' })).toBeVisible()
}

export async function openHousehold(page: Page): Promise<void> {
  await navLink(page, 'Household').click()
  await expect(page.getByRole('heading', { name: 'Household' })).toBeVisible()
}

export async function readInviteCode(page: Page): Promise<string> {
  const code = (await page.getByTestId('invite-code').innerText()).trim()
  expect(code).toMatch(/^[A-Z2-9]{8}$/)
  return code
}

export async function signOut(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL((url) => url.pathname === '/signin')
}
