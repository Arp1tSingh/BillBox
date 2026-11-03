/**
 * Offline capture queue.
 *
 * Bills selected with no connection (or whose upload never reached the API)
 * are stored in IndexedDB. The provider flushes them when the browser comes
 * back online. Queue entries are scoped to the signed-in user so one account
 * can never upload another account's bill.
 */

const DB_NAME = 'billbox'
const DB_VERSION = 1
const STORE = 'uploads'

export interface QueuedFile {
  name: string
  type: string
  lastModified: number
  /**
   * Page bytes. ArrayBuffers are stored instead of Blob/File objects because
   * WebKit refuses to clone Blob values into IndexedDB.
   */
  data?: ArrayBuffer
  /** Legacy entries written before the ArrayBuffer migration. */
  blob?: Blob
}

export interface QueuedUpload {
  id: string
  userId: string
  createdAt: number
  skipAi: boolean
  attempts: number
  lastError: string | null
  /** Set once the API accepted the upload, so a failed cleanup cannot re-upload it. */
  receiptId?: string | null
  files: QueuedFile[]
}

function makeId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('Offline saving is not available in this browser.'))
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE)) {
        const store = database.createObjectStore(STORE, { keyPath: 'id' })
        store.createIndex('userId', 'userId', { unique: false })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Could not open offline storage.'))
  })
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Offline storage failed.'))
  })
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error ?? new Error('Offline storage failed.'))
    transaction.onabort = () => reject(transaction.error ?? new Error('Offline storage was cancelled.'))
  })
}

export async function enqueueUpload(
  userId: string,
  files: File[],
  skipAi: boolean,
): Promise<QueuedUpload> {
  const database = await openDatabase()
  try {
    const item: QueuedUpload = {
      id: makeId(),
      userId,
      createdAt: Date.now(),
      skipAi,
      attempts: 0,
      lastError: null,
      receiptId: null,
      files: await Promise.all(
        files.map(async (file) => ({
          name: file.name,
          type: file.type,
          lastModified: file.lastModified,
          data: await file.arrayBuffer(),
        })),
      ),
    }
    const transaction = database.transaction(STORE, 'readwrite')
    transaction.objectStore(STORE).add(item)
    await transactionDone(transaction)
    return item
  } finally {
    database.close()
  }
}

export async function listQueuedUploads(userId: string): Promise<QueuedUpload[]> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(STORE, 'readonly')
    const index = transaction.objectStore(STORE).index('userId')
    const items = await requestResult(index.getAll(userId) as IDBRequest<QueuedUpload[]>)
    return items.sort((left, right) => left.createdAt - right.createdAt)
  } finally {
    database.close()
  }
}

export async function removeQueuedUpload(id: string): Promise<void> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(STORE, 'readwrite')
    transaction.objectStore(STORE).delete(id)
    await transactionDone(transaction)
  } finally {
    database.close()
  }
}

export async function markQueuedUploadError(id: string, message: string): Promise<void> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(STORE, 'readwrite')
    const store = transaction.objectStore(STORE)
    const item = await requestResult(store.get(id) as IDBRequest<QueuedUpload | undefined>)
    if (item) {
      store.put({ ...item, attempts: item.attempts + 1, lastError: message })
    }
    await transactionDone(transaction)
  } finally {
    database.close()
  }
}

export async function markQueuedUploadUploaded(id: string, receiptId: string): Promise<void> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(STORE, 'readwrite')
    const store = transaction.objectStore(STORE)
    const item = await requestResult(store.get(id) as IDBRequest<QueuedUpload | undefined>)
    if (item) {
      store.put({ ...item, receiptId, lastError: null })
    }
    await transactionDone(transaction)
  } finally {
    database.close()
  }
}

export function fileFromQueued(item: QueuedFile): File {
  const source = item.data ?? item.blob
  if (!source) {
    throw new Error('Queued file is unreadable. Discard it and save the bill again.')
  }
  return new File([source], item.name, {
    type: item.type,
    lastModified: item.lastModified,
  })
}
