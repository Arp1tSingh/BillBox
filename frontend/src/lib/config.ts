const env = import.meta.env

export const config = {
  supabaseUrl: (env.VITE_SUPABASE_URL as string | undefined) ?? '',
  supabaseAnonKey: (env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? '',
  apiBaseUrl: ((env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000').replace(
    /\/$/,
    '',
  ),
}

export const isSupabaseConfigured = Boolean(config.supabaseUrl && config.supabaseAnonKey)
