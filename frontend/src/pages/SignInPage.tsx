import { ReceiptText } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthProvider'
import { ErrorAlert } from '../components/ErrorAlert'
import { FullPageSpinner } from '../components/FullPageSpinner'

type Mode = 'signin' | 'signup'

export function SignInPage() {
  const { user, loading, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (loading) return <FullPageSpinner label="Checking your session" />
  if (user) {
    const destination = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    setSubmitting(true)
    try {
      if (mode === 'signin') {
        await signIn(email.trim(), password)
        navigate('/', { replace: true })
      } else {
        const result = await signUp(email.trim(), password)
        if (result.needsConfirmation) {
          setNotice('Check your email to confirm the account, then sign in.')
        } else {
          navigate('/onboarding', { replace: true })
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not sign in. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  function switchMode() {
    setMode(mode === 'signin' ? 'signup' : 'signin')
    setError(null)
    setNotice(null)
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top,_#ccfbf1,_#f8fafc_45%)] px-5 py-12">
      <div className="w-full max-w-md">
        <div className="mb-7 flex items-center gap-3">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-teal-700 text-white shadow-sm shadow-teal-900/20">
            <ReceiptText size={24} aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">BillBox</h1>
            <p className="text-sm text-slate-600">Every household bill, findable.</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            {mode === 'signin' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {mode === 'signin'
              ? 'Sign in with the email you use for your household.'
              : 'Use an email and a password of at least 8 characters.'}
          </p>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                placeholder="At least 8 characters"
              />
            </div>

            <ErrorAlert message={error} />
            {notice ? (
              <p className="rounded-xl border border-teal-200 bg-teal-50 px-3 py-2.5 text-sm text-teal-800">
                {notice}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? 'One moment…' : mode === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <button
            type="button"
            onClick={switchMode}
            className="mt-4 w-full rounded-xl px-2 py-2 text-sm font-medium text-teal-800 transition hover:bg-teal-50"
          >
            {mode === 'signin' ? 'New to BillBox? Create an account' : 'Already have an account? Sign in'}
          </button>
        </div>

        <p className="mt-5 text-center text-xs leading-5 text-slate-500">
          Bills stay inside your household. Sensitive documents can skip AI in the next build
          section.
        </p>
      </div>
    </main>
  )
}
