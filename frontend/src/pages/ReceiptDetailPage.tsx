import {
  ArrowLeft,
  Check,
  Clock,
  FileText,
  Loader2,
  Plus,
  RotateCcw,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ErrorAlert } from '../components/ErrorAlert'
import { FullPageSpinner } from '../components/FullPageSpinner'
import {
  useAddReceiptTag,
  useDeleteReceipt,
  useProcessReceipt,
  useReceipt,
  useRemoveReceiptTag,
  useUpdateReceipt,
} from '../hooks/useReceipts'
import type { ReceiptDetail } from '../lib/types'

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
  if (!value) return '—'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function ReceiptDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: receipt, error, isLoading } = useReceipt(id)
  const process = useProcessReceipt(id ?? '')
  const update = useUpdateReceipt(id ?? '')
  const addTag = useAddReceiptTag(id ?? '')
  const removeTag = useRemoveReceiptTag(id ?? '')
  const remove = useDeleteReceipt(id ?? '')

  if (isLoading) return <FullPageSpinner label="Loading your bill" />
  if (error) {
    return (
      <div>
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal-800">
          <ArrowLeft size={15} aria-hidden="true" />
          Back to Home
        </Link>
        <div className="mt-4">
          <ErrorAlert message={error.message} />
        </div>
      </div>
    )
  }
  if (!receipt) return null

  async function handleDelete() {
    if (!window.confirm('Delete this bill and its pages? This cannot be undone.')) return
    await remove.mutateAsync().catch(() => null)
    navigate('/', { replace: true })
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal-800 hover:underline"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Back to Home
        </Link>
        <button
          type="button"
          onClick={handleDelete}
          disabled={remove.isPending}
          className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
        >
          <Trash2 size={15} aria-hidden="true" />
          {remove.isPending ? 'Deleting…' : 'Delete'}
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {receipt.title ?? receipt.merchant ?? 'Bill'}
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            {formatAmount(receipt.amount, receipt.currency)}
            {receipt.bill_date ? ` · ${formatDate(receipt.bill_date)}` : ''}
          </p>
        </div>
        <StatusBadge status={receipt.status} aiSkipped={receipt.ai_skipped} />
      </div>

      <ErrorAlert message={remove.error?.message} />

      {receipt.status === 'failed' ? (
        <section className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 p-4">
          <p className="text-sm font-semibold text-rose-900">
            {receipt.failure_reason ?? 'Could not read this bill.'}
          </p>
          <p className="mt-1 text-xs text-rose-800">
            Your pages are safe. Retry when you are ready.
          </p>
          <button
            type="button"
            onClick={() => process.mutate()}
            disabled={process.isPending}
            className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-rose-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose-800 disabled:opacity-60"
          >
            <RotateCcw size={15} aria-hidden="true" />
            {process.isPending ? 'Retrying…' : 'Retry'}
          </button>
          <ErrorAlert message={process.error?.message} />
        </section>
      ) : null}

      {receipt.status === 'processing' ? (
        <section className="mt-5 flex items-center gap-3 rounded-2xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
          <Loader2 size={18} className="animate-spin" aria-hidden="true" />
          <div>
            <p className="font-semibold">Reading your bill…</p>
            <p className="text-xs text-teal-800">This page refreshes on its own.</p>
          </div>
        </section>
      ) : null}

      <ReceiptFields key={`${receipt.id}-${receipt.status}`} receipt={receipt} update={update} />

      <TagEditor receipt={receipt} addTag={addTag} removeTag={removeTag} />

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Pages</h2>
        {receipt.pages.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No pages stored.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {receipt.pages.map((page) =>
              page.mime_type === 'application/pdf' ? (
                <object
                  key={page.page_no}
                  data={page.url ?? ''}
                  type="application/pdf"
                  className="h-[70vh] w-full rounded-xl border border-slate-200"
                  aria-label="Bill PDF"
                >
                  <p className="p-4 text-sm text-slate-600">
                    <a href={page.url ?? '#'} className="font-semibold text-teal-800 underline">
                      Open the PDF
                    </a>
                  </p>
                </object>
              ) : (
                <a
                  key={page.page_no}
                  href={page.url ?? '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="block overflow-hidden rounded-xl border border-slate-200"
                >
                  <img
                    src={page.url ?? ''}
                    alt={`Bill page ${page.page_no}`}
                    className="w-full bg-slate-50 object-contain"
                  />
                </a>
              ),
            )}
          </div>
        )}
        <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
          <FileText size={13} aria-hidden="true" />
          Page links expire after an hour and only your household can open them.
        </p>
      </section>
    </div>
  )
}

function StatusBadge({ status, aiSkipped }: { status: string; aiSkipped: boolean }) {
  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800">
        <Clock size={13} aria-hidden="true" />
        Processing
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="rounded-full bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-800">
        Needs attention
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800">
      <Check size={13} aria-hidden="true" />
      {aiSkipped ? 'Saved without AI' : 'Ready'}
    </span>
  )
}

function ReceiptFields({
  receipt,
  update,
}: {
  receipt: ReceiptDetail
  update: ReturnType<typeof useUpdateReceipt>
}) {
  const [title, setTitle] = useState(receipt.title ?? '')
  const [merchant, setMerchant] = useState(receipt.merchant ?? '')
  const [amount, setAmount] = useState(receipt.amount ?? '')
  const [billDate, setBillDate] = useState(receipt.bill_date ?? '')

  useEffect(() => {
    setTitle(receipt.title ?? '')
    setMerchant(receipt.merchant ?? '')
    setAmount(receipt.amount ?? '')
    setBillDate(receipt.bill_date ?? '')
  }, [receipt.title, receipt.merchant, receipt.amount, receipt.bill_date])

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await update
      .mutateAsync({
        title: title.trim() || null,
        merchant: merchant.trim() || null,
        amount: amount ? amount : null,
        bill_date: billDate || null,
      })
      .catch(() => null)
  }

  return (
    <form
      className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      onSubmit={handleSave}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-900">Details</h2>
        <button
          type="submit"
          disabled={update.isPending}
          className="rounded-xl bg-teal-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:opacity-60"
        >
          {update.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Field label="Title" id="receipt-title">
          <input
            id="receipt-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          />
        </Field>
        <Field label="Merchant" id="receipt-merchant">
          <input
            id="receipt-merchant"
            value={merchant}
            onChange={(event) => setMerchant(event.target.value)}
            maxLength={200}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          />
        </Field>
        <Field label="Amount" id="receipt-amount">
          <input
            id="receipt-amount"
            type="number"
            inputMode="decimal"
            min="0"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          />
        </Field>
        <Field label="Bill date" id="receipt-date">
          <input
            id="receipt-date"
            type="date"
            value={billDate}
            onChange={(event) => setBillDate(event.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          />
        </Field>
      </div>
      <ErrorAlert message={update.error?.message} />
    </form>
  )
}

function Field({
  label,
  id,
  children,
}: {
  label: string
  id: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </label>
      {children}
    </div>
  )
}

function TagEditor({
  receipt,
  addTag,
  removeTag,
}: {
  receipt: ReceiptDetail
  addTag: ReturnType<typeof useAddReceiptTag>
  removeTag: ReturnType<typeof useRemoveReceiptTag>
}) {
  const [label, setLabel] = useState('')

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const clean = label.trim()
    if (!clean) return
    await addTag.mutateAsync({ label: clean }).catch(() => null)
    setLabel('')
  }

  return (
    <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Tags</h2>
      {receipt.tags.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">
          {receipt.ai_skipped ? 'No tags yet. Add one below.' : 'No tags yet.'}
        </p>
      ) : (
        <ul className="mt-3 flex flex-wrap gap-2">
          {receipt.tags.map((tag) => (
            <li
              key={tag.tag_id}
              className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 pl-3 pr-1.5 py-1 text-xs font-semibold text-slate-700"
            >
              {tag.label_en}
              <span className="rounded-full bg-white px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                {tag.source}
              </span>
              <button
                type="button"
                onClick={() => removeTag.mutate(tag.tag_id)}
                disabled={removeTag.isPending}
                aria-label={`Remove ${tag.label_en} tag`}
                className="grid h-5 w-5 place-items-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-rose-600"
              >
                <X size={12} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="mt-3 flex gap-2" onSubmit={handleAdd}>
        <label htmlFor="tag-label" className="sr-only">
          New tag
        </label>
        <input
          id="tag-label"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          maxLength={80}
          placeholder="Add a tag, e.g. warranty"
          className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
        <button
          type="submit"
          disabled={addTag.isPending || !label.trim()}
          className="inline-flex items-center gap-1.5 rounded-xl border border-teal-700 px-3 py-2 text-sm font-semibold text-teal-800 transition hover:bg-teal-50 disabled:opacity-60"
        >
          <Plus size={14} aria-hidden="true" />
          Add
        </button>
      </form>
      <ErrorAlert message={addTag.error?.message ?? removeTag.error?.message} />
    </section>
  )
}
