import { LogOut, UsersRound } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthProvider'
import { ErrorAlert } from '../components/ErrorAlert'
import { FullPageSpinner } from '../components/FullPageSpinner'
import { useCreateHousehold, useHousehold, useJoinHousehold } from '../hooks/useHousehold'

export function OnboardingPage() {
  const { user, signOut } = useAuth()
  const { data: household, isLoading, error } = useHousehold()
  const createHousehold = useCreateHousehold()
  const joinHousehold = useJoinHousehold()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')

  if (isLoading) return <FullPageSpinner label="Checking your household" />
  if (household) return <Navigate to="/" replace />

  const membershipError = error && error.code !== 'no_household' ? error.message : null
  const mutationError = createHousehold.error?.message ?? joinHousehold.error?.message ?? null
  const busy = createHousehold.isPending || joinHousehold.isPending

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const created = await createHousehold.mutateAsync(name).catch(() => null)
    if (created) navigate('/', { replace: true })
  }

  async function handleJoin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const joined = await joinHousehold.mutateAsync(code).catch(() => null)
    if (joined) navigate('/', { replace: true })
  }

  async function handleSignOut() {
    await signOut()
    navigate('/signin', { replace: true })
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col px-5 py-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-700 text-white">
            <UsersRound size={20} aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-900">BillBox</p>
            <p className="text-xs text-slate-500">{user?.email}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          aria-label="Sign out"
          className="flex items-center gap-1.5 rounded-xl px-2.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          <LogOut size={16} aria-hidden="true" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>

      <div className="mt-10">
        <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">One last step</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
          Set up your household
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">
          Create a shared home for your bills, or join someone who already has one. A household can
          hold up to 8 people.
        </p>
      </div>

      <div className="mt-6 space-y-3">
        <ErrorAlert message={membershipError} />
        <ErrorAlert message={mutationError} />
      </div>

      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Create a household</h2>
          <p className="mt-1 text-sm text-slate-500">You become the owner and can invite others.</p>
          <form className="mt-4 space-y-3" onSubmit={handleCreate}>
            <div>
              <label htmlFor="household-name" className="mb-1.5 block text-sm font-medium text-slate-700">
                Household name
              </label>
              <input
                id="household-name"
                name="household-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={80}
                placeholder="Sharma home"
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
              />
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:opacity-60"
            >
              {createHousehold.isPending ? 'Creating…' : 'Create household'}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Join a household</h2>
          <p className="mt-1 text-sm text-slate-500">Ask the owner for the 8-character code.</p>
          <form className="mt-4 space-y-3" onSubmit={handleJoin}>
            <div>
              <label htmlFor="invite-code" className="mb-1.5 block text-sm font-medium text-slate-700">
                Invite code
              </label>
              <input
                id="invite-code"
                name="invite-code"
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                required
                minLength={8}
                maxLength={8}
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                placeholder="ABCD2345"
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 font-mono text-sm uppercase tracking-[0.18em] outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
              />
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl border border-teal-700 px-4 py-2.5 text-sm font-semibold text-teal-800 transition hover:bg-teal-50 disabled:opacity-60"
            >
              {joinHousehold.isPending ? 'Joining…' : 'Join household'}
            </button>
          </form>
        </section>
      </div>
    </main>
  )
}
