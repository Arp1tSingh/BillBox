import { createClient, type SupabaseClient } from '@supabase/supabase-js'

import { config, isSupabaseConfigured } from './config'

export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(config.supabaseUrl, config.supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null

export function requireSupabase(): SupabaseClient {
  if (!supabase) {
    throw new Error('Supabase is not configured. Add the VITE_SUPABASE_* values to .env.local.')
  }
  return supabase
}
