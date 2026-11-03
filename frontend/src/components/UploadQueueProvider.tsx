import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { useAuth } from '../auth/AuthProvider'
import { api, ApiError } from '../lib/api'
import type { ReceiptUploadResponse } from '../lib/types'
import {
  enqueueUpload,
  fileFromQueued,
  listQueuedUploads,
  markQueuedUploadError,
  markQueuedUploadUploaded,
  removeQueuedUpload,
  type QueuedUpload,
} from '../lib/uploadQueue'

interface UploadQueueValue {
  items: QueuedUpload[]
  syncing: boolean
  error: string | null
  enqueue: (files: File[], skipAi: boolean) => Promise<QueuedUpload>
  sync: () => Promise<void>
  remove: (id: string) => Promise<void>
}

const UploadQueueContext = createContext<UploadQueueValue | null>(null)

export function UploadQueueProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [items, setItems] = useState<QueuedUpload[]>([])
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const syncingRef = useRef(false)
  const userRef = useRef(user)
  userRef.current = user

  const refresh = useCallback(async () => {
    if (!user) {
      setItems([])
      return
    }
    try {
      setItems(await listQueuedUploads(user.id))
    } catch {
      // Private browsing or a blocked IndexedDB must not break the app.
    }
  }, [user])

  const sync = useCallback(async () => {
    if (!user || syncingRef.current || !navigator.onLine) return
    let queued: QueuedUpload[]
    try {
      queued = await listQueuedUploads(user.id)
    } catch {
      return
    }
    setItems(queued)
    if (queued.length === 0) return

    syncingRef.current = true
    setSyncing(true)
    setError(null)
    try {
      for (const item of queued) {
        // The session can change while a retry loop is running.
        if (userRef.current?.id !== user.id) break

        try {
          let receiptId = item.receiptId ?? null
          if (!receiptId) {
            const form = new FormData()
            for (const file of item.files) {
              const restored = fileFromQueued(file)
              form.append('files[]', restored, restored.name)
            }
            form.append('skip_ai', item.skipAi ? 'true' : 'false')
            const created = await api.upload<ReceiptUploadResponse>('/receipts', form)
            receiptId = created.id
            // Persist the ID before doing anything else. If the browser closes
            // now, the next sync resumes instead of creating a duplicate bill.
            await markQueuedUploadUploaded(item.id, receiptId)
          }
          if (!item.skipAi) {
            try {
              await api.post(`/receipts/${receiptId}/process`)
            } catch {
              // The receipt exists; the detail screen offers Retry.
            }
          }
          await removeQueuedUpload(item.id)
          setItems((current) => current.filter((entry) => entry.id !== item.id))
        } catch (caught) {
          const message =
            caught instanceof ApiError ? caught.message : 'No connection yet. Will keep trying.'
          try {
            await markQueuedUploadError(item.id, message)
          } catch {
            // A blocked IndexedDB leaves the item in place; show the error.
          }
          setError(message)
          break
        }
      }
      void queryClient.invalidateQueries({ queryKey: ['receipts'] })
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
    } finally {
      syncingRef.current = false
      setSyncing(false)
      await refresh()
    }
  }, [queryClient, refresh, user])

  const enqueue = useCallback(
    async (files: File[], skipAi: boolean) => {
      if (!user) throw new Error('Sign in before saving a bill offline.')
      const item = await enqueueUpload(user.id, files, skipAi)
      setError(null)
      await refresh()
      return item
    },
    [refresh, user],
  )

  const remove = useCallback(
    async (id: string) => {
      await removeQueuedUpload(id)
      await refresh()
    },
    [refresh],
  )

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!user) return
    function handleOnline() {
      void sync()
    }
    window.addEventListener('online', handleOnline)
    if (navigator.onLine) void sync()
    return () => window.removeEventListener('online', handleOnline)
  }, [sync, user])

  return (
    <UploadQueueContext.Provider value={{ items, syncing, error, enqueue, sync, remove }}>
      {children}
    </UploadQueueContext.Provider>
  )
}

export function useUploadQueue(): UploadQueueValue {
  const value = useContext(UploadQueueContext)
  if (!value) throw new Error('useUploadQueue must be used inside UploadQueueProvider.')
  return value
}
