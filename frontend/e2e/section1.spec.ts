import { expect, test } from './fixtures/test'
import {
  addMembers,
  countMembers,
  deleteUserByEmail,
  getHouseholdForUser,
  isMember,
  resetTestState,
  signIn as apiSignIn,
} from './helpers/admin'
import * as ui from './helpers/app'
import { env } from './helpers/env'
import { allSeededUsers } from './helpers/users'

test.beforeEach(async ({ users }) => {
  await resetTestState(allSeededUsers(users))
})

test('E2E-1.1 sign up, reload, sign out', async ({ page }) => {
  const email = `e2e-signup-${Date.now()}@example.com`
  try {
    await ui.signUp(page, email)
    await expect(page).toHaveURL((url) => url.pathname === '/onboarding')
    await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()

    await page.reload()
    await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()
    await expect(page).toHaveURL((url) => url.pathname === '/onboarding')

    await ui.signOut(page)
  } finally {
    await deleteUserByEmail(email)
  }
})

test('E2E-1.2 create household', async ({ page, users }) => {
  const name = `Sharma home ${Date.now()}`

  await ui.signIn(page, users.owner)
  await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()

  await ui.createHousehold(page, name)
  await expect(page.getByRole('banner').getByText(name)).toBeVisible()
  await expect(page.getByText('No bills yet')).toBeVisible()

  await ui.openHousehold(page)
  await ui.readInviteCode(page)
  await expect(page.getByTestId('member-count')).toHaveText('1 member')
  await expect(page.getByTestId('current-role')).toHaveText('owner')
  await expect(page.getByText(users.owner.email)).toBeVisible()
})

test('E2E-1.3 second account joins with code', async ({ page, users }) => {
  const name = `Shared home ${Date.now()}`

  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, name)
  await ui.openHousehold(page)
  const code = await ui.readInviteCode(page)

  await ui.signOut(page)
  await ui.signIn(page, users.member)
  await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()

  await ui.joinHousehold(page, code)
  await ui.openHousehold(page)

  await expect(page.getByTestId('member-count')).toHaveText('2 members')
  await expect(page.getByTestId('current-role')).toHaveText('member')
  await expect(page.getByText(users.member.email)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Rotate code' })).toHaveCount(0)
})

test('E2E-1.4 ninth account cannot join a full household', async ({ page, users }) => {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Full home ${Date.now()}`)

  const household = await getHouseholdForUser(users.owner.id)
  if (!household) throw new Error('Owner has no household after creation')
  await addMembers(household.id, users.fillers)
  expect(await countMembers(household.id)).toBe(8)

  await ui.signOut(page)
  await ui.signIn(page, users.outsider)
  await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()

  await page.getByLabel('Invite code').fill(household.invite_code)
  await page.getByRole('button', { name: 'Join household' }).click()

  await expect(page.getByRole('alert')).toContainText(/full/i)
  await expect(page).toHaveURL((url) => url.pathname === '/onboarding')
  expect(await countMembers(household.id)).toBe(8)
  expect(await isMember(household.id, users.outsider.id)).toBe(false)
})

test('E2E-1.5 outsider cannot read household data', async ({ page, request, users }) => {
  await ui.signIn(page, users.owner)
  await ui.createHousehold(page, `Private home ${Date.now()}`)
  const household = await getHouseholdForUser(users.owner.id)
  if (!household) throw new Error('Owner has no household after creation')

  await ui.signOut(page)
  await ui.signIn(page, users.outsider)
  await expect(page.getByRole('heading', { name: 'Set up your household' })).toBeVisible()
  await expect(page.getByText(household.name)).toHaveCount(0)

  const session = await apiSignIn(users.outsider.email)
  const apiResponse = await request.get(`${env.apiBaseUrl}/households/me`, {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
      'X-Household-Id': household.id,
    },
  })
  expect(apiResponse.status()).toBe(403)
  const body = (await apiResponse.json()) as { error?: { code?: string } }
  expect(body.error?.code).toBe('not_a_member')

  const postgrest = await request.get(
    `${env.supabaseUrl}/rest/v1/households?select=id&id=eq.${household.id}`,
    {
      headers: {
        apikey: env.anonKey,
        Authorization: `Bearer ${session.access_token}`,
      },
    },
  )
  expect(postgrest.status()).toBe(200)
  expect(await postgrest.json()).toEqual([])
})

test('E2E-1.6 keep-alive heartbeat is readable with the anon key', async ({ request }) => {
  const response = await request.get(
    `${env.supabaseUrl}/rest/v1/heartbeat?select=id,last_ping&limit=1`,
    {
      headers: {
        apikey: env.anonKey,
        Authorization: `Bearer ${env.anonKey}`,
      },
    },
  )
  expect(response.status()).toBe(200)
  const rows = (await response.json()) as Array<{ id: number; last_ping: string }>
  expect(rows).toHaveLength(1)
  expect(rows[0]?.last_ping).toBeTruthy()
})

test('E2E-1.7 deployed smoke', async ({ page, request }) => {
  test.skip(
    !env.deployedAppUrl || !env.deployedApiUrl,
    'Set E2E_DEPLOYED_APP_URL and E2E_DEPLOYED_API_URL to run the deployed smoke test.',
  )

  const health = await request.get(`${env.deployedApiUrl}/health`)
  expect(health.status()).toBe(200)
  const body = (await health.json()) as { status?: string }
  expect(body.status).toBe('ok')

  await page.goto(env.deployedAppUrl)
  await expect(page.getByRole('heading', { name: 'BillBox' })).toBeVisible()
})
