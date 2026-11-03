import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Camera,
  CloudOff,
  FileText,
  ImagePlus,
  Loader2,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { ErrorAlert } from '../components/ErrorAlert'
import { useUploadQueue } from '../components/UploadQueueProvider'
import { api, ApiError } from '../lib/api'
import {
  ImageError,
  preparePages,
  releasePages,
  totalBytes,
  type PreparedPage,
} from '../lib/image'
import type { ReceiptUploadResponse } from '../lib/types'

export function ScanPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { enqueue } = useUploadQueue()
  const cameraRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)
  const [pages, setPages] = useState<PreparedPage[]>([])
  const [skipAi, setSkipAi] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState<string | null>(null)

  const hasPdf = pages.some((page) => page.isPdf)
  const sizeMb = (totalBytes(pages) / (1024 * 1024)).toFixed(1)

  async function addFiles(list: FileList | null) {
    if (!list || list.length === 0) return
    setError(null)
    setNotice(null)
    const files = Array.from(list)
    try {
      const prepared = await preparePages(files, pages.length)
      const nextPdf = [...pages, ...prepared].filter((page) => page.isPdf).length
      if (nextPdf > 1 || (nextPdf === 1 && pages.length + prepared.length > 1)) {
        releasePages(prepared)
        throw new ImageError('Upload one PDF on its own, or up to 10 images.')
      }
      setPages((current) => [...current, ...prepared])
    } catch (caught) {
      setError(caught instanceof ImageError ? caught.message : 'Could not add that file.')
    }
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    void addFiles(event.target.files)
    event.target.value = ''
  }

  function removePage(index: number) {
    setPages((current) => {
      const page = current[index]
      if (page?.previewUrl) URL.revokeObjectURL(page.previewUrl)
      return current.filter((_, position) => position !== index)
    })
  }

  function movePage(index: number, delta: number) {
    setPages((current) => {
      const target = index + delta
      if (target < 0 || target >= current.length) return current
      const next = [...current]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  async function saveForLater() {
    setError(null)
    try {
      await enqueue(
        pages.map((page) => page.file),
        skipAi,
      )
      releasePages(pages)
      setPages([])
      setNotice('Saved offline. This bill will upload automatically when you are back online.')
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Could not save this bill offline. Try again when you have a connection.',
      )
    } finally {
      setBusy(false)
      setPhase(null)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pages.length === 0) {
      setError('Add at least one page first.')
      return
    }
    setError(null)
    setNotice(null)
    setBusy(true)

    if (!navigator.onLine) {
      await saveForLater()
      return
    }

    setPhase('Uploading your bill…')

    const form = new FormData()
    for (const page of pages) {
      form.append('files[]', page.file, page.file.name)
    }
    form.append('skip_ai', skipAi ? 'true' : 'false')

    let created: ReceiptUploadResponse
    try {
      created = await api.upload<ReceiptUploadResponse>('/receipts', form)
    } catch (caught) {
      if (!(caught instanceof ApiError)) {
        // A fetch failure means the request never reached the API (for example,
        // the connection dropped after the page loaded). Keep the bill instead
        // of making the user select the pages again.
        await saveForLater()
        return
      }
      setError(caught.message)
      setBusy(false)
      setPhase(null)
      return
    }

    if (!skipAi) {
      setPhase('Reading your bill…')
      try {
        await api.post(`/receipts/${created.id}/process`)
      } catch {
        // The detail screen can retry; the upload itself succeeded.
      }
    }

    void queryClient.invalidateQueries({ queryKey: ['receipts'] })
    void queryClient.invalidateQueries({ queryKey: ['tags'] })
    releasePages(pages)
    navigate(`/receipts/${created.id}`, { replace: true })
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Scan</h1>
      <p className="mt-1 text-sm text-slate-600">
        Capture a bill with the camera or add pages from your files.
      </p>

      <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => cameraRef.current?.click()}
            disabled={busy}
            className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border border-teal-200 bg-teal-50 px-4 py-5 text-sm font-semibold text-teal-800 transition hover:border-teal-300 hover:bg-teal-100 disabled:opacity-60"
          >
            <Camera size={24} aria-hidden="true" />
            Take a photo
          </button>
          <button
            type="button"
            onClick={() => galleryRef.current?.click()}
            disabled={busy}
            className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-5 text-sm font-semibold text-slate-700 transition hover:border-teal-200 hover:text-teal-800 disabled:opacity-60"
          >
            <ImagePlus size={24} aria-hidden="true" />
            Add pages or a PDF
          </button>
        </div>

        <input
          ref={cameraRef}
          type="file"
          accept="image/*,application/pdf"
          capture="environment"
          className="sr-only"
          aria-label="Take a photo of a bill"
          onChange={handleInput}
        />
        <input
          ref={galleryRef}
          type="file"
          accept="image/*,application/pdf"
          multiple
          className="sr-only"
          aria-label="Add bill pages or a PDF"
          onChange={handleInput}
        />

        <ErrorAlert message={error} />

        {notice ? (
          <p
            role="status"
            className="flex items-start gap-2 rounded-xl border border-teal-200 bg-teal-50 px-3 py-2.5 text-xs leading-5 text-teal-900"
          >
            <CloudOff size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            {notice}
          </p>
        ) : null}

        {pages.length > 0 ? (
          <section aria-label="Selected pages" className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-slate-900">
                {pages.length} {pages.length === 1 ? 'page' : 'pages'}
              </h2>
              <p className="text-xs text-slate-500">
                {sizeMb} MB {hasPdf ? '· PDF' : ''}
              </p>
            </div>
            <ol className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {pages.map((page, index) => (
                <li
                  key={page.id}
                  className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-50"
                >
                  {page.previewUrl ? (
                    <img
                      src={page.previewUrl}
                      alt={`Page ${index + 1}`}
                      className="aspect-[3/4] w-full object-cover"
                    />
                  ) : (
                    <div className="flex aspect-[3/4] w-full flex-col items-center justify-center gap-2 text-slate-500">
                      <FileText size={30} aria-hidden="true" />
                      <span className="max-w-full truncate px-2 text-xs">{page.file.name}</span>
                    </div>
                  )}
                  <span className="absolute left-2 top-2 rounded-full bg-slate-900/75 px-2 py-0.5 text-xs font-semibold text-white">
                    {index + 1}
                  </span>
                  <div className="absolute inset-x-1 bottom-1 flex items-center justify-between gap-1">
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => movePage(index, -1)}
                        disabled={index === 0 || busy}
                        aria-label={`Move page ${index + 1} earlier`}
                        className="rounded-lg bg-white/90 p-1.5 text-slate-700 shadow-sm disabled:opacity-40"
                      >
                        <ArrowLeft size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        onClick={() => movePage(index, 1)}
                        disabled={index === pages.length - 1 || busy}
                        aria-label={`Move page ${index + 1} later`}
                        className="rounded-lg bg-white/90 p-1.5 text-slate-700 shadow-sm disabled:opacity-40"
                      >
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => removePage(index)}
                      disabled={busy}
                      aria-label={`Remove page ${index + 1}`}
                      className="rounded-lg bg-white/90 p-1.5 text-rose-600 shadow-sm disabled:opacity-40"
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        <section className="rounded-2xl border border-slate-200 bg-white p-4">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={skipAi}
              onChange={(event) => setSkipAi(event.target.checked)}
              disabled={busy}
              className="mt-0.5 h-5 w-5 rounded border-slate-300 text-teal-700"
            />
            <span>
              <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
                <Sparkles size={15} aria-hidden="true" />
                Skip AI for this bill
              </span>
              <span className="mt-0.5 block text-xs leading-5 text-slate-500">
                Use this for Aadhaar, PAN or bank statements. You will add the details and tags
                yourself.
              </span>
            </span>
          </label>

          {!skipAi ? (
            <p className="mt-3 flex gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
              AI reads this bill. On the free tier, submitted content may be used to improve
              Google products and may be reviewed by people. Do not upload ID or bank documents
              with AI on.
            </p>
          ) : null}
        </section>

        <button
          type="submit"
          disabled={busy || pages.length === 0}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-teal-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : null}
          {busy ? phase : 'Save bill'}
        </button>
      </form>
    </div>
  )
}
