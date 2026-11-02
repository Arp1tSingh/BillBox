import { ArrowRight, ReceiptText } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useHousehold } from '../hooks/useHousehold'

export function HomePage() {
  const { data: household } = useHousehold()

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">
            {household?.name}
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Home</h1>
          <p className="mt-1 text-sm text-slate-600">
            Everything your household has saved, in one place.
          </p>
        </div>
        <Link
          to="/household"
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-800"
        >
          Invite someone
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>

      <div className="mt-6">
        <label htmlFor="search" className="mb-1.5 block text-sm font-medium text-slate-700">
          Search bills
        </label>
        <input
          id="search"
          type="search"
          disabled
          placeholder="Search arrives in Section 4"
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-400"
        />
      </div>

      <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-12 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-teal-50 text-teal-700">
          <ReceiptText size={26} aria-hidden="true" />
        </span>
        <h2 className="mt-4 text-base font-semibold text-slate-900">No bills yet</h2>
        <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-500">
          Camera capture and AI extraction arrive in the next build section. Your household is ready
          for its first receipt.
        </p>
        <Link
          to="/scan"
          className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800"
        >
          Open Scan
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </section>
    </div>
  )
}
