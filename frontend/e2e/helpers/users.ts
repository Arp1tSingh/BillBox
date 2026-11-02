import { readFileSync } from 'node:fs'
import path from 'node:path'

import type { TestUser } from './admin'
import { repoRoot } from './env'

export interface SeedUsers {
  owner: TestUser
  member: TestUser
  outsider: TestUser
  fillers: TestUser[]
}

const usersFile = path.join(repoRoot, 'frontend', 'e2e', '.auth', 'users.json')

export function loadUsers(): SeedUsers {
  return JSON.parse(readFileSync(usersFile, 'utf8')) as SeedUsers
}

export function allSeededUsers(users: SeedUsers): TestUser[] {
  return [users.owner, users.member, users.outsider, ...users.fillers]
}
