import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { FullPageSpinner } from '../components/FullPageSpinner'
import { useAuth } from './AuthProvider'

export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <FullPageSpinner label="Checking your session" />
  if (!user) {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
