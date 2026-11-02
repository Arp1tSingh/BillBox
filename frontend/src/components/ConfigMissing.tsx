import { config } from '../lib/config'

export function ConfigMissing() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-5 py-12">
      <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">BillBox</p>
      <h1 className="mt-2 text-2xl font-bold text-slate-900">Configuration needed</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        The frontend has no Supabase credentials. Create <code>frontend/.env.local</code> with the
        local Supabase values, then restart the dev server.
      </p>
      <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs leading-6 text-slate-100">
        {`VITE_SUPABASE_URL=${config.supabaseUrl || 'http://127.0.0.1:54321'}
VITE_SUPABASE_ANON_KEY=<anon key>
VITE_API_BASE_URL=${config.apiBaseUrl}`}
      </pre>
      <p className="mt-4 text-xs text-slate-500">
        Run <code>npx supabase status</code> to print the local anon key.
      </p>
    </main>
  )
}
