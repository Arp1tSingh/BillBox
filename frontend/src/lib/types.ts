export type Role = 'owner' | 'member'

export interface HouseholdMember {
  user_id: string
  email: string | null
  role: Role
  joined_at: string
}

export interface Household {
  id: string
  name: string
  invite_code: string
  role: Role
  created_at: string
  members: HouseholdMember[]
}
