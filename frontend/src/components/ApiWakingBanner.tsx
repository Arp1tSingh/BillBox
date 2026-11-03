import { Loader2 } from 'lucide-react'
import { useSyncExternalStore } from 'react'

import { isApiWaking, subscribeApiActivity } from '../lib/apiActivity'

export function ApiWakingBanner() {
  const waking = useSyncExternalStore(subscribeApiActivity, isApiWaking, () => false)
  if (!waking) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="border-t border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs font-medium text-amber-900"
    >
      <span className="inline-flex items-center gap-1.5">
        <Loader2 size={12} className="animate-spin" aria-hidden="true" />
        Waking up the server…
      </span>
    </div>
  )
}
