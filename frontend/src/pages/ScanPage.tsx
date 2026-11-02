import { Camera } from 'lucide-react'
import { Link } from 'react-router-dom'

export function ScanPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Scan</h1>
      <p className="mt-1 text-sm text-slate-600">Capture a bill with the camera or upload a PDF.</p>

      <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-14 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-teal-50 text-teal-700">
          <Camera size={26} aria-hidden="true" />
        </span>
        <h2 className="mt-4 text-base font-semibold text-slate-900">Capture arrives next</h2>
        <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-500">
          Section 2 adds camera capture, multi-page uploads, the skip-AI switch and extraction
          status.
        </p>
        <Link to="/" className="mt-5 inline-flex text-sm font-semibold text-teal-800 hover:underline">
          Back to Home
        </Link>
      </section>
    </div>
  )
}
