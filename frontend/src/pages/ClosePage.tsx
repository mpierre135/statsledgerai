import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, formatMoney } from '../components'
import {
  approveAccrual,
  closeMonth,
  flagNeedsInfo,
  getAccruals,
  getAnomalies,
  getCloseChecklist,
  getPayees,
} from '../api'

export function ClosePage() {
  const { clientId = '' } = useParams()
  const [payees, setPayees] = useState<any[]>([])
  const [anomalies, setAnomalies] = useState<any[]>([])
  const [accruals, setAccruals] = useState<any[]>([])
  const [periodEnd, setPeriodEnd] = useState('2025-03-31')
  const [checklist, setChecklist] = useState<any | null>(null)
  const [msg, setMsg] = useState('')

  const reload = () => {
    getPayees(clientId).then(setPayees)
    getAnomalies(clientId).then(setAnomalies)
    getAccruals(clientId).then(setAccruals)
    getCloseChecklist(clientId, periodEnd).then(setChecklist)
  }

  useEffect(() => {
    if (clientId) reload()
  }, [clientId, periodEnd])

  return (
    <div className="space-y-4">
      <Card title="Month-end close checklist">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <label className="text-sm">
            Period end{' '}
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="ml-2 rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
          <button
            className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
            disabled={!checklist?.can_close}
            onClick={async () => {
              const res = await closeMonth(clientId, periodEnd)
              setMsg(`Closed through ${res.close_date}`)
              reload()
            }}
          >
            Close month
          </button>
          <button
            className="rounded-lg border border-amber-500/50 px-3 py-1.5 text-xs"
            onClick={async () => {
              const res = await closeMonth(clientId, periodEnd, true)
              setMsg(`Force-closed through ${res.close_date}`)
              reload()
            }}
          >
            Force close
          </button>
        </div>
        {checklist && (
          <div className="text-sm">
            Anomalies: {checklist.anomaly_count} · Blocking: {checklist.blocking_count} ·{' '}
            <span className={checklist.can_close ? 'text-emerald-600' : 'text-amber-600'}>
              {checklist.can_close ? 'Ready to close' : 'Resolve blocking items first'}
            </span>
          </div>
        )}
        {msg && <div className="mt-2 text-sm text-emerald-600">{msg}</div>}
      </Card>

      <Card title="Anomaly detection">
        <div className="space-y-2">
          {anomalies.map((a, i) => (
            <div key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
              <div>
                <span className="mr-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] uppercase text-amber-700">{a.severity}</span>
                <span className="mr-2 text-xs text-slate-500">{a.type}</span>
                {a.message}
              </div>
              <button
                className="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600"
                onClick={async () => {
                  await flagNeedsInfo(clientId, {
                    question: `Please clarify: ${a.message}`,
                    tx_ref: a.tx_ref,
                    payee: a.payee,
                    amount: a.amount,
                    tx_date: a.date,
                  })
                  setMsg('Flagged as Needs Info for client portal')
                }}
              >
                Flag Needs Info
              </button>
            </div>
          ))}
          {!anomalies.length && <div className="text-sm text-slate-500">No anomalies detected.</div>}
        </div>
      </Card>

      <Card title="Payee grouping">
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="px-2 py-1 text-left">Payee</th>
                <th className="px-2 py-1 text-right">Count</th>
                <th className="px-2 py-1 text-right">Total</th>
                <th className="px-2 py-1 text-left">Accounts</th>
              </tr>
            </thead>
            <tbody>
              {payees.map((p) => (
                <tr key={p.payee} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="px-2 py-1">
                    {p.payee}
                    {p.mixed_accounts && (
                      <span className="ml-2 rounded bg-amber-500/20 px-1 text-[10px] text-amber-700">mixed</span>
                    )}
                  </td>
                  <td className="px-2 py-1 text-right">{p.count}</td>
                  <td className="px-2 py-1 text-right font-mono-amount">{formatMoney(p.total)}</td>
                  <td className="px-2 py-1 text-xs text-slate-500">{p.accounts.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Accrual / prepaid schedules (preview → approve)">
        {accruals.map((a, i) => (
          <div key={i} className="mb-4 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <div className="font-medium">
              {a.payee} · {formatMoney(a.total)} over {a.periods} months
            </div>
            <div className="text-xs text-slate-500">{a.narration}</div>
            <div className="mt-2 overflow-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr>
                    <th className="text-left">Date</th>
                    <th className="text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {a.schedule.map((s: any) => (
                    <tr key={s.date}>
                      <td>{s.date}</td>
                      <td className="text-right font-mono-amount">{s.amount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button
              className="mt-3 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs text-white"
              onClick={async () => {
                const res = await approveAccrual(clientId, {
                  schedule: a.schedule,
                  expense_account: a.expense_account,
                  prepaid_account: a.prepaid_account,
                  payee: a.payee,
                })
                setMsg(`Posted ${res.posted} amortization entries`)
                reload()
              }}
            >
              Approve schedule (post through today)
            </button>
          </div>
        ))}
        {!accruals.length && <div className="text-sm text-slate-500">No accrual candidates found.</div>}
      </Card>
    </div>
  )
}
