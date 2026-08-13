import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, formatMoney } from '../components'
import { acceptImport, previewImport, sendToInbox } from '../api'

export function ImportPage() {
  const { clientId = '' } = useParams()
  const [preview, setPreview] = useState<any | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [selected, setSelected] = useState<Record<number, boolean>>({})

  const onFile = async (file: File) => {
    setBusy(true)
    setMessage('')
    try {
      const data = await previewImport(clientId, file)
      setPreview(data)
      const init: Record<number, boolean> = {}
      data.rows.forEach((r: any, i: number) => {
        init[i] = !r.possible_duplicate && !r.needs_review
      })
      setSelected(init)
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || String(e))
    } finally {
      setBusy(false)
    }
  }

  const acceptSelected = async () => {
    if (!preview) return
    setBusy(true)
    try {
      const rows = preview.rows
        .map((r: any, i: number) => ({ r, i }))
        .filter(({ i }: any) => selected[i])
        .map(({ r }: any) => ({
          date: r.date,
          amount: r.amount,
          payee: r.payee,
          narration: r.narration,
          account: r.classification.account,
          fingerprint: r.fingerprint,
          force_duplicate: !!r.possible_duplicate,
        }))
      const res = await acceptImport(clientId, { rows })
      setMessage(`Posted ${res.posted}, skipped duplicates ${res.skipped_duplicates}`)
    } catch (e: any) {
      setMessage(JSON.stringify(e?.response?.data?.detail || e.message))
    } finally {
      setBusy(false)
    }
  }

  const toInbox = async () => {
    if (!preview) return
    const rows = preview.rows.filter((_: any, i: number) => selected[i] || preview.rows[i].needs_review)
    const needs = preview.rows.filter((r: any) => r.needs_review)
    const res = await sendToInbox(clientId, needs.length ? needs : rows)
    setMessage(`Sent ${res.created} rows to review inbox`)
  }

  return (
    <div className="space-y-4">
      <Card title="Bank import (CSV / OFX / QFX)">
        <p className="mb-3 text-sm text-slate-500">
          Three-layer cake classifies each row. Confidence under {preview?.threshold ?? 85}% goes amber for review.
          Duplicates are unchecked by default.
        </p>
        <input
          type="file"
          accept=".csv,.ofx,.qfx,text/csv"
          disabled={busy}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        {message && <div className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{message}</div>}
      </Card>

      {preview && (
        <Card
          title={`Preview · ${preview.count} rows`}
          action={
            <div className="flex gap-2">
              <button
                disabled={busy}
                onClick={toInbox}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-600"
              >
                Send low-confidence to inbox
              </button>
              <button
                disabled={busy}
                onClick={acceptSelected}
                className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                Accept selected
              </button>
            </div>
          }
        >
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-2 py-2"></th>
                  <th className="px-2 py-2 text-left">Date</th>
                  <th className="px-2 py-2 text-left">Payee</th>
                  <th className="px-2 py-2 text-right">Amount</th>
                  <th className="px-2 py-2 text-left">Account</th>
                  <th className="px-2 py-2 text-left">Confidence</th>
                  <th className="px-2 py-2 text-left">Reason</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r: any, i: number) => {
                  const low = r.classification.confidence < (preview.threshold || 85)
                  return (
                    <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-2 py-2">
                        <input
                          type="checkbox"
                          checked={!!selected[i]}
                          onChange={(e) => setSelected((s) => ({ ...s, [i]: e.target.checked }))}
                        />
                      </td>
                      <td className="px-2 py-2 whitespace-nowrap">{r.date}</td>
                      <td className="px-2 py-2">
                        {r.payee}
                        {r.possible_duplicate && (
                          <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
                            duplicate?
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-2 text-right font-mono-amount">{formatMoney(r.amount)}</td>
                      <td className="px-2 py-2 text-xs">{r.classification.account}</td>
                      <td className="px-2 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            low
                              ? 'bg-amber-500/20 text-amber-700 dark:text-amber-300'
                              : 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300'
                          }`}
                        >
                          {r.classification.confidence}% · {r.classification.layer}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-xs text-slate-500 max-w-md">{r.classification.reason}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
