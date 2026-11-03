import { ArrowRight, Loader2, ReceiptText, RotateCcw, Search, X } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useHousehold } from '../hooks/useHousehold'
import {
  useProcessReceipt,
  useReceipts,
  useTags,
  type ReceiptSearchParams,
} from '../hooks/useReceipts'
import type { ReceiptSummary, TagView } from '../lib/types'

const PAGE_SIZE = 20

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
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const selectedTags = searchParams.getAll('tag')
  const sort = searchParams.get('sort') ?? 'date'
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1)

  const params: ReceiptSearchParams = {
    q: query || undefined,
    tag: selectedTags,
    from: searchParams.get('from') ?? undefined,
    to: searchParams.get('to') ?? undefined,
    min: searchParams.get('min') ?? undefined,
    max: searchParams.get('max') ?? undefined,
    sort,
    page,
    page_size: PAGE_SIZE,
  }

  const { data: receipts, isLoading, error } = useReceipts(params)
  const { data: tags } = useTags()
  const [term, setTerm] = useState(query)
  const hasFilters = Boolean(query || selectedTags.length || params.from || params.to || params.min || params.max)

  useEffect(() => {
    setTerm(query)
  }, [query])

  const chips = (tags ?? []).filter(
    (tag) => tag.count > 0 || selectedTags.includes(tag.slug),
  )
  const total = receipts?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function update(mutate: (next: URLSearchParams) => void) {
    const next = new URLSearchParams(searchParams)
    mutate(next)
    setSearchParams(next)
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    update((next) => {
      const clean = term.trim()
      if (clean) next.set('q', clean)
      else next.delete('q')
      next.delete('page')
    })
  }

  function toggleTag(tag: TagView) {
    update((next) => {
      const current = next.getAll('tag')
      next.delete('tag')
      const nextTags = current.includes(tag.slug)
        ? current.filter((value) => value !== tag.slug)
        : [...current, tag.slug]
      for (const value of nextTags) next.append('tag', value)
      next.delete('page')
    })
  }

  function changeSort(value: string) {
    update((next) => {
      if (value === 'date') next.delete('sort')
      else next.set('sort', value)
      next.delete('page')
    })
  }

  function clearFilters() {
    setSearchParams(new URLSearchParams())
    setTerm('')
  }

  function goToPage(nextPage: number) {
    update((next) => {
      if (nextPage <= 1) next.delete('page')
      else next.set('page', String(nextPage))
    })
  }

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

      <form className="mt-6" onSubmit={handleSearch} role="search">
        <label htmlFor="search" className="mb-1.5 block text-sm font-medium text-slate-700">
          Search bills
        </label>
        <div className="flex gap-2">
          <div className="relative min-w-0 flex-1">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              id="search"
              type="search"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Try “electricity over 2000” or “पाणी last month”"
              className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            />
          </div>
          <button
            type="submit"
            className="rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800"
          >
            Search
          </button>
        </div>
      </form>

      {chips.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-1.5" aria-label="Filter by tag">
          {chips.map((tag) => {
            const active = selectedTags.includes(tag.slug)
            return (
              <button
                key={tag.id}
                type="button"
                onClick={() => toggleTag(tag)}
                aria-pressed={active}
                className={[
                  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold transition',
                  active
                    ? 'border-teal-700 bg-teal-700 text-white'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-teal-300 hover:text-teal-800',
                ].join(' ')}
              >
                {tag.label_en}
                <span
                  className={[
                    'rounded-full px-1.5 text-[10px]',
                    active ? 'bg-teal-800 text-teal-50' : 'bg-slate-100 text-slate-500',
                  ].join(' ')}
                >
                  {tag.count}
                </span>
              </button>
            )
          })}
          {hasFilters ? (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            >
              <X size={12} aria-hidden="true" />
              Clear
            </button>
          ) : null}
        </div>
      ) : null}

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

      {!isLoading && receipts && receipts.items.length > 0 ? (
        <section className="mt-6" aria-label="Bills">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">
              {hasFilters ? 'Results' : 'Recent bills'}
              {hasFilters ? <span className="ml-1.5 font-normal text-slate-500">({total})</span> : null}
            </h2>
            <label className="flex items-center gap-1.5 text-xs text-slate-500">
              Sort
              <select
                value={sort}
                onChange={(event) => changeSort(event.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700"
              >
                <option value="date">Date</option>
                <option value="amount">Amount</option>
                <option value="relevance">Relevance</option>
              </select>
            </label>
          </div>
          <ul className="mt-3 space-y-2.5">
            {receipts.items.map((receipt) => (
              <ReceiptCard key={receipt.id} receipt={receipt} />
            ))}
          </ul>

          {totalPages > 1 ? (
            <nav className="mt-4 flex items-center justify-between" aria-label="Pages">
              <button
                type="button"
                onClick={() => goToPage(page - 1)}
                disabled={page <= 1}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
              >
                Previous
              </button>
              <p className="text-xs text-slate-500">
                Page {page} of {totalPages}
              </p>
              <button
                type="button"
                onClick={() => goToPage(page + 1)}
                disabled={page >= totalPages}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
              >
                Next
              </button>
            </nav>
          ) : null}
        </section>
      ) : null}

      {!isLoading && receipts && receipts.items.length === 0 ? (
        hasFilters ? (
          <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-10 text-center">
            <h2 className="text-base font-semibold text-slate-900">No bills match that search</h2>
            <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-500">
              Try a different keyword, or remove a filter.
            </p>
            <button
              type="button"
              onClick={clearFilters}
              className="mt-4 rounded-xl border border-teal-700 px-4 py-2.5 text-sm font-semibold text-teal-800 hover:bg-teal-50"
            >
              Clear search
            </button>
          </section>
        ) : (
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
        )
      ) : null}
    </div>
  )
}

function ReceiptCard({ receipt }: { receipt: ReceiptSummary }) {
  const process = useProcessReceipt(receipt.id)
  const subtitle = receipt.merchant ?? receipt.title ?? receipt.bill_type ?? 'Bill'

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
