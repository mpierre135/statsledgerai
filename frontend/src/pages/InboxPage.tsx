import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, formatMoney } from '../components'
import { acceptInbox, getAccounts, getInbox } from '../api'

export function InboxPage() {
  const { clientId = '' } = useParams()
  const [items, setItems] = useState<any[]>([])
  const [accounts, setAccounts] = useState<any[]>([])
  const [accountMap, setAccountMap] = useState<Record<number, string>>({})
  const [msg, setMsg] = useState('')

  const reload = () => {
    getInbox(clientId).then(setItems)
    getAccounts(clientId).then(setAccounts)
  }

  useEffect(() => {
    if (clientId) reload()
  }, [clientId])

  const post = async (item: any) => {
    const account = accountMap[item.id] || item.suggested_account
    if (!account) return
    await acceptInbox(clientId, item.id, { account })
    setMsg(`Posted inbox #${item.id} to ${account}`)
    reload()
  }

  return (
    <div className="space-y-4">
      <Card title="Review inbox">
        <p className="mb-3 text-sm text-slate-500">
          Correct-before-accept: change the account if the suggestion is wrong. Corrections feed Layers 1–2.
        </p>
        {msg && <div className="mb-3 text-sm text-emerald-600">{msg}</div>}
        {!items.length && <div className="text-sm text-slate-500">Inbox is empty. Import low-confidence rows to populate it.</div>}
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-medium">
                    {item.payee} · <span className="font-mono-amount">{formatMoney(item.amount)}</span>
                  </div>
                  <div className="text-xs text-slate-500">
                    {item.tx_date} · {item.layer} · {item.confidence}%
                  </div>
                  <div className="mt-1 text-xs text-amber-700 dark:text-amber-300">{item.reason}</div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900"
                    value={accountMap[item.id] || item.suggested_account || ''}
                    onChange={(e) => setAccountMap((m) => ({ ...m, [item.id]: e.target.value }))}
                  >
                    {accounts
                      .filter((a) => a.is_leaf)
                      .map((a) => (
                        <option key={a.name} value={a.name}>
                          {a.name}
                        </option>
                      ))}
                  </select>
                  <button
                    onClick={() => post(item)}
                    className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white"
                  >
                    Accept
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
