import { Download, Home, LogOut, ReceiptText, ScanLine, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthProvider'
import { ApiWakingBanner } from './ApiWakingBanner'
import { useHousehold } from '../hooks/useHousehold'

const navItems = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/scan', label: 'Scan', icon: ScanLine, end: false },
  { to: '/household', label: 'Household', icon: Users, end: false },
]

function navClass(active: boolean): string {
  return [
    'flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition',
    active ? 'bg-teal-50 text-teal-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  ].join(' ')
}

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function Layout() {
  const { signOut } = useAuth()
  const { data: household } = useHousehold()
  const navigate = useNavigate()
  const [installPrompt, setInstallPrompt] = useState<InstallPromptEvent | null>(null)

  useEffect(() => {
    function handlePrompt(event: Event) {
      event.preventDefault()
      setInstallPrompt(event as InstallPromptEvent)
    }
    window.addEventListener('beforeinstallprompt', handlePrompt)
    return () => window.removeEventListener('beforeinstallprompt', handlePrompt)
  }, [])

  async function install() {
    if (!installPrompt) return
    await installPrompt.prompt()
    setInstallPrompt(null)
  }

  async function handleSignOut() {
    await signOut()
    navigate('/signin', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-teal-700 text-white">
              <ReceiptText size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold leading-4 text-slate-900">BillBox</p>
              <p className="truncate text-xs text-slate-500">
                {household?.name ?? 'Your household'}
              </p>
            </div>
          </div>

          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => navClass(isActive)}>
                <item.icon size={16} aria-hidden="true" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          {installPrompt ? (
            <button
              type="button"
              onClick={install}
              className="hidden items-center gap-1.5 rounded-xl px-2.5 py-2 text-sm font-medium text-teal-800 transition hover:bg-teal-50 sm:flex"
            >
              <Download size={16} aria-hidden="true" />
              Install
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleSignOut}
            aria-label="Sign out"
            className="flex items-center gap-1.5 rounded-xl px-2.5 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            <LogOut size={16} aria-hidden="true" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
        <ApiWakingBanner />
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 pb-28 pt-6 md:pb-12">
        <Outlet />
      </main>

      <nav
        className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1.5 backdrop-blur md:hidden"
        aria-label="Primary"
      >
        <div className="mx-auto flex max-w-md items-stretch justify-around px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                [
                  'flex min-h-12 min-w-20 flex-col items-center justify-center gap-1 rounded-xl px-2 text-xs font-medium',
                  isActive ? 'text-teal-800' : 'text-slate-500',
                ].join(' ')
              }
            >
              <item.icon size={20} aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
