import { AlertCircle } from 'lucide-react'

export function ErrorAlert({ message }: { message: string | null | undefined }) {
  if (!message) return null
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800"
    >
      <AlertCircle className="mt-0.5 shrink-0" size={16} aria-hidden="true" />
      <span>{message}</span>
    </div>
  )
}
