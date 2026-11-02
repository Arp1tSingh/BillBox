import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center px-5">
      <div className="text-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">404</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">That page is not here</h1>
        <p className="mt-2 text-sm text-slate-600">The link may be old, or the bill was deleted.</p>
        <Link
          to="/"
          className="mt-5 inline-flex rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800"
        >
          Back to BillBox
        </Link>
      </div>
    </main>
  )
}
