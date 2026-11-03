import { ArrowRight, Loader2, ReceiptText, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useHousehold } from '../hooks/useHousehold'
import { useProcessReceipt, useReceipts } from '../hooks/useReceipts'
import type { ReceiptSummary } from '../lib/types'

function formatAmount(amount: string | null, currency: string): string {
  if (amount === null) return '—'
  const value = Number(amount)
  if (Number.isNaN(value)) return amount
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: currency || 'INR',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatDate(value: string | null): string {
  if (!value) return ''
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function HomePage() {
  const { data: household } = useHousehold()
  const { data: receipts, isLoading, error } = useReceipts()

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
          placeholder="Search arrives in the next build section"
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-400"
        />
      </div>

      {error ? (
        <p className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800">
          {error.message}
        </p>
      ) : null}

      {isLoading ? (
        <div className="mt-6 flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          Loading your bills…
        </div>
      ) : null}

      {!isLoading && receipts && receipts.length === 0 ? (
        <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-12 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-teal-50 text-teal-700">
            <ReceiptText size={26} aria-hidden="true" />
          </span>
          <h2 className="mt-4 text-base font-semibold text-slate-900">No bills yet</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-500">
            Scan your first bill and it will show up here, ready to search and edit.
          </p>
          <Link
            to="/scan"
            className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800"
          >
            Scan a bill
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </section>
      ) : null}

      {receipts && receipts.length > 0 ? (
        <section className="mt-6" aria-label="Recent bills">
          <h2 className="text-sm font-semibold text-slate-900">Recent bills</h2>
          <ul className="mt-3 space-y-2.5">
            {receipts.map((receipt) => (
              <ReceiptCard key={receipt.id} receipt={receipt} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

function ReceiptCard({ receipt }: { receipt: ReceiptSummary }) {
  const process = useProcessReceipt(receipt.id)
  const subtitle =
    receipt.merchant ?? receipt.title ?? (receipt.bill_type ?? 'Bill')

  return (
    <li className="rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:border-teal-200">
      <Link to={`/receipts/${receipt.id}`} className="flex items-center gap-3 p-3">
        <span className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100 text-slate-400">
          {receipt.thumbnail_url ? (
            <img
              src={receipt.thumbnail_url}
              alt=""
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <ReceiptText size={22} aria-hidden="true" />
          )}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-900">
              {receipt.title ?? subtitle}
            </span>
            {receipt.status === 'processing' ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                <Loader2 size={10} className="animate-spin" aria-hidden="true" />
                Reading
              </span>
            ) : null}
            {receipt.status === 'failed' ? (
              <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-800">
                Failed
              </span>
            ) : null}
          </span>
          <span className="mt-0.5 block truncate text-xs text-slate-500">
            {subtitle}
            {receipt.bill_date ? ` · ${formatDate(receipt.bill_date)}` : ''}
          </span>
          {receipt.status === 'failed' && receipt.failure_reason ? (
            <span className="mt-0.5 block truncate text-xs text-rose-700">
              {receipt.failure_reason}
            </span>
          ) : null}
        </span>

        <span className="shrink-0 text-sm font-semibold text-slate-900">
          {formatAmount(receipt.amount, receipt.currency)}
        </span>
      </Link>

      {receipt.status === 'failed' ? (
        <div className="border-t border-slate-100 px-3 py-2">
          <button
            type="button"
            onClick={() => process.mutate()}
            disabled={process.isPending}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-800 hover:underline disabled:opacity-60"
          >
            <RotateCcw size={13} aria-hidden="true" />
            {process.isPending ? 'Retrying…' : 'Retry extraction'}
          </button>
        </div>
      ) : null}
    </li>
  )
}
