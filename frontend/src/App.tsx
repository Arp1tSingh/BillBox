import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { RequireAuth } from './auth/RequireAuth'
import { ConfigMissing } from './components/ConfigMissing'
import { ErrorAlert } from './components/ErrorAlert'
import { FullPageSpinner } from './components/FullPageSpinner'
import { Layout } from './components/Layout'
import { useHousehold } from './hooks/useHousehold'
import { isSupabaseConfigured } from './lib/config'
import { HomePage } from './pages/HomePage'
import { HouseholdPage } from './pages/HouseholdPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { ReceiptDetailPage } from './pages/ReceiptDetailPage'
import { ScanPage } from './pages/ScanPage'
import { SignInPage } from './pages/SignInPage'

function RequireHousehold() {
  const { data, error, isLoading, refetch } = useHousehold()

  if (isLoading) return <FullPageSpinner label="Loading your household" />
  if (error) {
    if (error.code === 'no_household') return <Navigate to="/onboarding" replace />
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 px-5">
        <ErrorAlert message={error.message} />
        <button
          type="button"
          onClick={() => void refetch()}
          className="rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800"
        >
          Try again
        </button>
      </main>
    )
  }
  if (!data) return <Navigate to="/onboarding" replace />
  return <Outlet />
}

export default function App() {
  if (!isSupabaseConfigured) return <ConfigMissing />

  return (
    <Routes>
      <Route path="/signin" element={<SignInPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route element={<RequireHousehold />}>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="scan" element={<ScanPage />} />
            <Route path="receipts/:id" element={<ReceiptDetailPage />} />
            <Route path="household" element={<HouseholdPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
