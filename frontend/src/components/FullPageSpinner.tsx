export function FullPageSpinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="grid min-h-[60vh] place-items-center" role="status">
      <div className="flex flex-col items-center gap-3 text-sm text-slate-500">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-teal-700" />
        <span>{label}…</span>
      </div>
    </div>
  )
}
