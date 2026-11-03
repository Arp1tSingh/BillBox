let pending = 0
let waking = false
let timer: ReturnType<typeof setTimeout> | null = null
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export function beginApiRequest(): void {
  pending += 1
  if (pending === 1 && timer === null) {
    timer = setTimeout(() => {
      timer = null
      if (pending > 0) {
        waking = true
        emit()
      }
    }, 1500)
  }
}

export function endApiRequest(): void {
  pending = Math.max(0, pending - 1)
  if (pending > 0) return
  if (timer !== null) {
    clearTimeout(timer)
    timer = null
  }
  if (waking) {
    waking = false
    emit()
  }
}

export function subscribeApiActivity(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function isApiWaking(): boolean {
  return waking
}
