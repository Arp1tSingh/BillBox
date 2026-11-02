import { Check, Copy, RefreshCw, Share2, Users } from 'lucide-react'
import { useState } from 'react'

import { ErrorAlert } from '../components/ErrorAlert'
import { FullPageSpinner } from '../components/FullPageSpinner'
import { useHousehold, useRotateInvite } from '../hooks/useHousehold'

export function HouseholdPage() {
  const { data: household, isLoading } = useHousehold()
  const rotate = useRotateInvite()
  const [copied, setCopied] = useState(false)

  if (isLoading || !household) return <FullPageSpinner label="Loading your household" />

  const isOwner = household.role === 'owner'

  async function copyCode() {
    if (!household) return
    try {
      await navigator.clipboard.writeText(household.invite_code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  async function shareCode() {
    if (!household || !navigator.share) return
    try {
      await navigator.share({
        title: `Join ${household.name} on BillBox`,
        text: `Use invite code ${household.invite_code} to join our household on BillBox.`,
      })
    } catch {
      // The user dismissed the share sheet.
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Household</h1>
      <p className="mt-1 text-sm text-slate-600">Invite people and see who shares this shelf.</p>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{household.name}</h2>
            <p className="mt-1 text-sm text-slate-500">
              Share this code with someone you want in the household.
            </p>
          </div>
          <span
            data-testid="current-role"
            className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold capitalize text-teal-800"
          >
            {household.role}
          </span>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <code
            data-testid="invite-code"
            className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 font-mono text-lg font-semibold tracking-[0.2em] text-slate-900"
          >
            {household.invite_code}
          </code>
          <button
            type="button"
            onClick={copyCode}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-800"
          >
            {copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
            {copied ? 'Copied' : 'Copy code'}
          </button>
          <button
            type="button"
            onClick={shareCode}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-800"
          >
            <Share2 size={15} aria-hidden="true" />
            Share
          </button>
          {isOwner ? (
            <button
              type="button"
              onClick={() => rotate.mutate()}
              disabled={rotate.isPending}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-800 disabled:opacity-60"
            >
              <RefreshCw size={15} aria-hidden="true" />
              {rotate.isPending ? 'Rotating…' : 'Rotate code'}
            </button>
          ) : null}
        </div>

        <div className="mt-3">
          <ErrorAlert message={rotate.error?.message} />
        </div>
        {!isOwner ? (
          <p className="mt-3 text-xs text-slate-500">
            Only the owner can rotate the invite code.
          </p>
        ) : null}
      </section>

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Users size={18} className="text-teal-700" aria-hidden="true" />
            <h2 className="text-base font-semibold text-slate-900">Members</h2>
          </div>
          <p data-testid="member-count" className="text-sm text-slate-500">
            {household.members.length} {household.members.length === 1 ? 'member' : 'members'}
          </p>
        </div>

        <ul className="mt-4 divide-y divide-slate-100">
          {household.members.map((member) => (
            <li key={member.user_id} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">
                  {member.email ?? 'Household member'}
                </p>
                <p className="text-xs text-slate-500">
                  Joined {new Date(member.joined_at).toLocaleDateString()}
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-600">
                {member.role}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
