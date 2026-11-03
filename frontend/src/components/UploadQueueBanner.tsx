import { CloudOff, Loader2, RefreshCw, X } from 'lucide-react'

import { useUploadQueue } from './UploadQueueProvider'

export function UploadQueueBanner() {
  const { items, syncing, error, sync, remove } = useUploadQueue()
  if (items.length === 0) return null

  const label = items.length === 1 ? 'bill' : 'bills'

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="upload-queue-banner"
      className="border-t border-amber-200 bg-amber-50"
    >
      <div className="mx-auto flex max-w-3xl items-start gap-3 px-4 py-2.5">
        {syncing ? (
          <Loader2 size={16} className="mt-0.5 shrink-0 animate-spin text-amber-800" aria-hidden="true" />
        ) : (
          <CloudOff size={16} className="mt-0.5 shrink-0 text-amber-800" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1 text-xs leading-5 text-amber-950">
          <p className="font-semibold">
            {syncing ? `Uploading ${items.length} saved ${label}…` : `${items.length} ${label} saved offline`}
          </p>
          <p className="text-amber-900/80">
            {error ??
              (syncing
                ? 'Keep this tab open until the upload finishes.'
                : 'BillBox uploads automatically when you are back online.')}
          </p>
        </div>
        {syncing ? null : (
          <button
            type="button"
            onClick={() => void sync()}
            className="flex shrink-0 items-center gap-1 rounded-lg bg-amber-100 px-2 py-1.5 text-xs font-semibold text-amber-900 transition hover:bg-amber-200"
          >
            <RefreshCw size={13} aria-hidden="true" />
            Retry now
          </button>
        )}
        <button
          type="button"
          onClick={() => void remove(items[0].id)}
          aria-label="Discard saved bill"
          className="shrink-0 rounded-lg p-1.5 text-amber-900/70 transition hover:bg-amber-100 hover:text-amber-950"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
