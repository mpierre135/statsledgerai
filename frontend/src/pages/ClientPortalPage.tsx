import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPortal, submitPortal, uploadPortal } from '../api'

export function ClientPortalPage() {
  const { token = '' } = useParams()
  const [data, setData] = useState<any | null>(null)
  const [error, setError] = useState('')
  const [memo, setMemo] = useState<Record<string, string>>({})
  const [category, setCategory] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState('')

  useEffect(() => {
    getPortal(token)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || 'Invalid link'))
  }, [token])

  if (error) {
    return (
      <div className="flex min-h-full items-center justify-center bg-[#0F172A] p-6 text-slate-50">
        <div className="rounded-xl border border-amber-500/40 bg-[#1E293B] p-6">{error}</div>
      </div>
    )
  }

  if (!data) {
    return <div className="min-h-full bg-[#0F172A] p-6 text-slate-300">Loading portal…</div>
  }

  return (
    <div className="min-h-full bg-[#0F172A] text-slate-50">
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-8">
          <div className="text-xs uppercase tracking-widest text-emerald-400">StatsLedger client portal</div>
          <h1 className="mt-1 text-2xl font-semibold">{data.client_name}</h1>
          <p className="mt-2 text-sm text-slate-400">
            No password needed. Tell us what these transactions were for — your bookkeeper will post them.
          </p>
        </div>

        {msg && <div className="mb-4 rounded-lg bg-emerald-500/15 p-3 text-sm text-emerald-300">{msg}</div>}

        <section className="mb-8 space-y-3">
          <h2 className="text-sm font-semibold text-slate-300">Uncategorized</h2>
          {data.uncategorized?.map((item: any) => (
            <div key={`u-${item.id}`} className="rounded-xl border border-slate-700 bg-[#1E293B] p-4">
              <div className="font-medium">
                {item.payee} · ${item.amount}
              </div>
              <div className="text-xs text-slate-400">{item.date}</div>
              <textarea
                className="mt-3 w-full rounded-lg border border-slate-600 bg-slate-900 p-2 text-sm"
                placeholder="What was this for?"
                value={memo[`u-${item.id}`] || ''}
                onChange={(e) => setMemo((m) => ({ ...m, [`u-${item.id}`]: e.target.value }))}
              />
              <select
                className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 p-2 text-sm"
                value={category[`u-${item.id}`] || ''}
                onChange={(e) => setCategory((c) => ({ ...c, [`u-${item.id}`]: e.target.value }))}
              >
                <option value="">Pick a category</option>
                {data.categories.map((c: string) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <div className="mt-2 flex flex-wrap gap-2">
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    if (!f) return
                    const up = await uploadPortal(token, f)
                    setMsg(`Receipt uploaded (${up.extracted?.merchant || 'parsed'}). Submitting…`)
                    await submitPortal(token, {
                      inbox_id: item.id,
                      memo: memo[`u-${item.id}`],
                      category: category[`u-${item.id}`],
                      receipt_stored_name: up.stored_name,
                    })
                    setMsg('Submitted for bookkeeper approval')
                  }}
                />
                <button
                  className="rounded-lg bg-emerald-500 px-3 py-1.5 text-sm text-white"
                  onClick={async () => {
                    await submitPortal(token, {
                      inbox_id: item.id,
                      memo: memo[`u-${item.id}`],
                      category: category[`u-${item.id}`],
                    })
                    setMsg('Submitted for bookkeeper approval')
                  }}
                >
                  Submit
                </button>
              </div>
            </div>
          ))}
          {!data.uncategorized?.length && <div className="text-sm text-slate-500">Nothing uncategorized.</div>}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-300">Needs info</h2>
          {data.needs_info?.map((item: any) => (
            <div key={`n-${item.id}`} className="rounded-xl border border-amber-500/30 bg-[#1E293B] p-4">
              <div className="text-sm text-amber-200">{item.question}</div>
              <div className="mt-1 text-xs text-slate-400">
                {item.payee} {item.amount ? `· $${item.amount}` : ''}
              </div>
              <textarea
                className="mt-3 w-full rounded-lg border border-slate-600 bg-slate-900 p-2 text-sm"
                placeholder="Your answer"
                value={memo[`n-${item.id}`] || ''}
                onChange={(e) => setMemo((m) => ({ ...m, [`n-${item.id}`]: e.target.value }))}
              />
              <button
                className="mt-2 rounded-lg bg-emerald-500 px-3 py-1.5 text-sm text-white"
                onClick={async () => {
                  await submitPortal(token, {
                    needs_info_id: item.id,
                    memo: memo[`n-${item.id}`],
                  })
                  setMsg('Answer submitted')
                }}
              >
                Submit answer
              </button>
            </div>
          ))}
          {!data.needs_info?.length && <div className="text-sm text-slate-500">No questions right now.</div>}
        </section>
      </div>
    </div>
  )
}
