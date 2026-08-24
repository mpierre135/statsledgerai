import { useEffect, useState } from 'react'
import { format, parseISO } from 'date-fns'
import { useParams } from 'react-router-dom'
import { Card, Kpi, LedgerBanner, formatMoney } from '../components'
import { API_BASE, getAccounts, getTransactions, getTrialBalance } from '../api'

export function LedgerPage() {
  const { clientId = '' } = useParams()
  const [txs, setTxs] = useState<any[]>([])
  const [tb, setTb] = useState<any[]>([])
  const [accounts, setAccounts] = useState<any[]>([])
  const [selected, setSelected] = useState<any | null>(null)

  const reload = () => {
    getTransactions(clientId).then(setTxs)
    getTrialBalance(clientId).then(setTb)
    getAccounts(clientId).then(setAccounts)
  }

  useEffect(() => {
    if (clientId) reload()
  }, [clientId])

  const bank = tb.find((r) => r.account.includes('Bank'))
  const expenses = tb.filter((r) => r.account.startsWith('Expenses:'))
  const expenseTotal = expenses.reduce((s, r) => s + Math.abs(Number(r.balance)), 0)

  return (
    <div className="space-y-4">
      <LedgerBanner clientId={clientId} />
      <div className="grid gap-4 md:grid-cols-4">
        <Kpi label="Transactions" value={String(txs.length)} />
        <Kpi label="Accounts" value={String(accounts.length)} />
        <Kpi label="Bank balance" value={formatMoney(bank?.balance || 0)} hint={bank?.account} />
        <Kpi label="Expense abs total" value={formatMoney(expenseTotal)} />
      </div>

      <div className={`flex flex-col gap-4 transition-all duration-300 lg:flex-row`}>
        <Card
          title="Journal"
          action={
            <div className="flex gap-2 text-xs">
              <a className="text-emerald-600 hover:underline" href={`${API_BASE}/clients/${clientId}/export/trial-balance.csv`}>
                CSV
              </a>
              <a className="text-emerald-600 hover:underline" href={`${API_BASE}/clients/${clientId}/export/trial-balance.xlsx`}>
                Excel
              </a>
            </div>
          }
        >
          <div className={`overflow-auto rounded-lg border border-slate-100 dark:border-slate-800 ${selected ? 'lg:w-full' : ''}`}>
            <table className="min-w-full text-left text-sm">
              <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Payee</th>
                  <th className="px-3 py-2">Narration</th>
                  <th className="px-3 py-2 text-right">Legs</th>
                </tr>
              </thead>
              <tbody>
                {txs.map((tx, i) => (
                  <tr
                    key={i}
                    onClick={() => setSelected(tx)}
                    className={`cursor-pointer border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60 ${
                      selected === tx ? 'bg-emerald-50 dark:bg-emerald-900/20' : ''
                    }`}
                  >
                    <td className="px-3 py-2 whitespace-nowrap">{format(parseISO(tx.date), 'MMM dd, yyyy')}</td>
                    <td className="px-3 py-2">{tx.payee}</td>
                    <td className="px-3 py-2 text-slate-500">{tx.narration}</td>
                    <td className="px-3 py-2 text-right font-mono-amount">{tx.postings.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {selected && (
          <Card title="Entry detail" action={<button className="text-xs text-slate-500" onClick={() => setSelected(null)}>Close</button>}>
            <div className="space-y-3 text-sm lg:w-80">
              <div>
                <div className="text-xs text-slate-500">Payee</div>
                <div className="font-medium">{selected.payee}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Narration</div>
                <div>{selected.narration || '—'}</div>
              </div>
              <div className="space-y-2">
                {selected.postings.map((p: any, i: number) => (
                  <div key={i} className="rounded-lg border border-slate-200 p-2 dark:border-slate-700">
                    <div className="flex justify-between gap-2">
                      <span className="text-xs">{p.account}</span>
                      <span className="font-mono-amount text-emerald-600 dark:text-emerald-400">{p.amount}</span>
                    </div>
                    {(p.meta?.class || p.meta?.location) && (
                      <div className="mt-1 text-[11px] text-slate-500">
                        {p.meta.class && <span className="mr-2">class:{p.meta.class}</span>}
                        {p.meta.location && <span>loc:{p.meta.location}</span>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </Card>
        )}
      </div>

      <Card title="Trial balance">
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="px-2 py-1 text-left">Account</th>
                <th className="px-2 py-1 text-right">Balance</th>
              </tr>
            </thead>
            <tbody>
              {tb.map((r) => (
                <tr key={r.account} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="px-2 py-1">{r.account}</td>
                  <td className="px-2 py-1 text-right font-mono-amount">{formatMoney(r.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
