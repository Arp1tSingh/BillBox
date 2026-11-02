import { existsSync } from 'node:fs'
import path from 'node:path'

import dotenv from 'dotenv'

function findRepoRoot(start: string): string {
  let current = start
  for (let depth = 0; depth < 6; depth += 1) {
    if (
      existsSync(path.join(current, 'BillBox-Blueprint.md')) ||
      existsSync(path.join(current, '.env.e2e.example'))
    ) {
      return current
    }
    const parent = path.dirname(current)
    if (parent === current) break
    current = parent
  }
  return path.resolve(start, '..')
}

export const repoRoot = findRepoRoot(process.cwd())

dotenv.config({ path: path.join(repoRoot, '.env.e2e') })
dotenv.config({ path: path.join(repoRoot, '.env.e2e.local'), override: true })

function trimSlash(value: string): string {
  return value.replace(/\/$/, '')
}

export const env = {
  supabaseUrl: trimSlash(process.env.SUPABASE_URL ?? ''),
  anonKey: process.env.SUPABASE_ANON_KEY ?? '',
  serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY ?? '',
  apiBaseUrl: trimSlash(process.env.API_BASE_URL ?? 'http://127.0.0.1:8000'),
  appUrl: trimSlash(process.env.APP_URL ?? 'http://127.0.0.1:5173'),
  deployedAppUrl: trimSlash(process.env.E2E_DEPLOYED_APP_URL ?? ''),
  deployedApiUrl: trimSlash(process.env.E2E_DEPLOYED_API_URL ?? ''),
}

export function assertE2EEnv(): void {
  const missing = [
    ['SUPABASE_URL', env.supabaseUrl],
    ['SUPABASE_ANON_KEY', env.anonKey],
    ['SUPABASE_SERVICE_ROLE_KEY', env.serviceRoleKey],
  ]
    .filter(([, value]) => !value)
    .map(([name]) => name)

  if (missing.length > 0) {
    throw new Error(
      `Missing E2E environment: ${missing.join(', ')}. Copy .env.e2e.example to .env.e2e and ` +
        'fill it from `npx supabase status`.',
    )
  }
}
