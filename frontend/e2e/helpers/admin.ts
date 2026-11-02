import { env } from './env'

export const TEST_PASSWORD = 'BillBox-e2e-123!'

export interface TestUser {
  id: string
  email: string
  password: string
}

interface SupabaseUser {
  id: string
  email?: string
}

interface SignInResult {
  access_token: string
  user: { id: string; email?: string }
}

export function serviceHeaders(): Record<string, string> {
  return {
    apikey: env.serviceRoleKey,
    Authorization: `Bearer ${env.serviceRoleKey}`,
    'Content-Type': 'application/json',
  }
}

export function anonHeaders(accessToken?: string): Record<string, string> {
  return {
    apikey: env.anonKey,
    Authorization: `Bearer ${accessToken ?? env.anonKey}`,
    'Content-Type': 'application/json',
  }
}

async function errorText(response: Response): Promise<string> {
  const body = await response.text()
  return `${response.status} ${response.statusText}: ${body}`
}

async function adminJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${env.supabaseUrl}/auth/v1/admin${path}`, {
    ...init,
    headers: { ...serviceHeaders(), ...(init.headers ?? {}) },
  })
  if (!response.ok) throw new Error(`Auth admin ${path} failed: ${await errorText(response)}`)
  return (await response.json()) as T
}

export async function listUsers(): Promise<SupabaseUser[]> {
  const body = await adminJson<{ users: SupabaseUser[] }>('/users?page=1&per_page=200')
  return body.users
}

export async function findUserByEmail(email: string): Promise<SupabaseUser | undefined> {
  const users = await listUsers()
  return users.find((user) => user.email?.toLowerCase() === email.toLowerCase())
}

export async function ensureUser(email: string): Promise<TestUser> {
  const create = await fetch(`${env.supabaseUrl}/auth/v1/admin/users`, {
    method: 'POST',
    headers: serviceHeaders(),
    body: JSON.stringify({ email, password: TEST_PASSWORD, email_confirm: true }),
  })

  if (create.ok) {
    const user = (await create.json()) as SupabaseUser
    return { id: user.id, email, password: TEST_PASSWORD }
  }

  const existing = await findUserByEmail(email)
  if (!existing) throw new Error(`Could not create or find ${email}: ${await errorText(create)}`)

  const update = await fetch(`${env.supabaseUrl}/auth/v1/admin/users/${existing.id}`, {
    method: 'PUT',
    headers: serviceHeaders(),
    body: JSON.stringify({ password: TEST_PASSWORD, email_confirm: true }),
  })
  if (!update.ok) throw new Error(`Could not reset ${email}: ${await errorText(update)}`)
  return { id: existing.id, email, password: TEST_PASSWORD }
}

export async function deleteUserByEmail(email: string): Promise<void> {
  const user = await findUserByEmail(email)
  if (!user) return
  await deleteUser(user.id)
}

export async function deleteUser(id: string): Promise<void> {
  const response = await fetch(`${env.supabaseUrl}/auth/v1/admin/users/${id}`, {
    method: 'DELETE',
    headers: serviceHeaders(),
  })
  if (!response.ok && response.status !== 404) {
    throw new Error(`Could not delete user ${id}: ${await errorText(response)}`)
  }
}

export async function signIn(email: string, password = TEST_PASSWORD): Promise<SignInResult> {
  const response = await fetch(`${env.supabaseUrl}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: anonHeaders(),
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) throw new Error(`Sign-in failed for ${email}: ${await errorText(response)}`)
  return (await response.json()) as SignInResult
}

interface HouseholdRow {
  id: string
  name: string
  invite_code: string
  created_by: string | null
}

async function rest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${env.supabaseUrl}/rest/v1/${path}`, {
    ...init,
    headers: { ...serviceHeaders(), ...(init.headers ?? {}) },
  })
  if (!response.ok) throw new Error(`PostgREST ${path} failed: ${await errorText(response)}`)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function getHouseholdForUser(userId: string): Promise<HouseholdRow | null> {
  const memberships = await rest<Array<{ household_id: string }>>(
    `household_members?select=household_id&user_id=eq.${userId}&limit=1`,
  )
  const householdId = memberships[0]?.household_id
  if (!householdId) return null
  const households = await rest<HouseholdRow[]>(
    `households?select=id,name,invite_code,created_by&id=eq.${householdId}&limit=1`,
  )
  return households[0] ?? null
}

export async function countMembers(householdId: string): Promise<number> {
  const rows = await rest<Array<{ user_id: string }>>(
    `household_members?select=user_id&household_id=eq.${householdId}`,
  )
  return rows.length
}

export async function isMember(householdId: string, userId: string): Promise<boolean> {
  const rows = await rest<Array<{ user_id: string }>>(
    `household_members?select=user_id&household_id=eq.${householdId}&user_id=eq.${userId}&limit=1`,
  )
  return rows.length > 0
}

export async function addMembers(
  householdId: string,
  users: TestUser[],
  role: 'owner' | 'member' = 'member',
): Promise<void> {
  const response = await fetch(`${env.supabaseUrl}/rest/v1/household_members`, {
    method: 'POST',
    headers: { ...serviceHeaders(), Prefer: 'return=minimal' },
    body: JSON.stringify(
      users.map((user) => ({ household_id: householdId, user_id: user.id, role })),
    ),
  })
  if (!response.ok) throw new Error(`Could not seed members: ${await errorText(response)}`)
}

export async function deleteHousehold(householdId: string): Promise<void> {
  await rest(`households?id=eq.${householdId}`, { method: 'DELETE' })
}

export async function resetTestState(users: TestUser[]): Promise<void> {
  if (users.length === 0) return
  const ids = users.map((user) => user.id).join(',')
  const householdIds = new Set<string>()

  const byMembership = await rest<Array<{ household_id: string }>>(
    `household_members?select=household_id&user_id=in.(${ids})`,
  )
  for (const row of byMembership) householdIds.add(row.household_id)

  const byCreator = await rest<Array<{ id: string }>>(
    `households?select=id&created_by=in.(${ids})`,
  )
  for (const row of byCreator) householdIds.add(row.id)

  for (const householdId of householdIds) {
    await deleteHousehold(householdId)
  }
}
