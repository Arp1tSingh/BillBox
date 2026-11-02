import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

import { ensureUser } from './helpers/admin'
import { assertE2EEnv, env, repoRoot } from './helpers/env'
import type { SeedUsers } from './helpers/users'

const authDirectory = path.join(repoRoot, 'frontend', 'e2e', '.auth')

async function waitForSupabase(): Promise<void> {
  const deadline = Date.now() + 60_000
  let lastError = ''

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${env.supabaseUrl}/auth/v1/health`, {
        headers: { apikey: env.anonKey },
      })
      if (response.ok) return
      lastError = `${response.status} ${response.statusText}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000))
  }

  throw new Error(
    `Supabase is not reachable at ${env.supabaseUrl} (${lastError}). Run \`npx supabase start\`.`,
  )
}

async function assertHeartbeat(): Promise<void> {
  const response = await fetch(
    `${env.supabaseUrl}/rest/v1/heartbeat?select=id,last_ping&limit=1`,
    { headers: { apikey: env.anonKey, Authorization: `Bearer ${env.anonKey}` } },
  )
  if (!response.ok) {
    throw new Error(`Heartbeat select failed: ${response.status} ${await response.text()}`)
  }
  const rows = (await response.json()) as unknown[]
  if (rows.length !== 1) {
    throw new Error(
      'Heartbeat row is missing. Run `npx supabase db reset` to apply migrations and seed.',
    )
  }
}

async function seedUsers(): Promise<SeedUsers> {
  const [owner, member, outsider] = await Promise.all([
    ensureUser('e2e-owner@example.com'),
    ensureUser('e2e-member@example.com'),
    ensureUser('e2e-outsider@example.com'),
  ])
  const fillers = await Promise.all(
    Array.from({ length: 7 }, (_, index) => ensureUser(`e2e-filler-${index + 1}@example.com`)),
  )
  return { owner, member, outsider, fillers }
}

export default async function globalSetup(): Promise<void> {
  assertE2EEnv()
  await waitForSupabase()
  await assertHeartbeat()

  const users = await seedUsers()
  await mkdir(authDirectory, { recursive: true })
  await writeFile(path.join(authDirectory, 'users.json'), JSON.stringify(users, null, 2))

  console.log(`Seeded ${3 + users.fillers.length} E2E accounts at ${env.supabaseUrl}`)
}
