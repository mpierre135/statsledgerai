import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, formatMoney } from '../components'
import { downloadAuthFile, getBookToTax, getChecklist, getPriorYears, uploadTaxDocs } from '../api'

export function TaxPage() {
  const { clientId = '' } = useParams()
  const [grid, setGrid] = useState<any | null>(null)
  const [checklist, setChecklist] = useState<any[]>([])
  const [priors, setPriors] = useState<any[]>([])
  const [msg, setMsg] = useState('')

  const reload = () => {
    getBookToTax(clientId).then(setGrid)
    getChecklist(clientId, 2025).then(setChecklist)
    getPriorYears(clientId).then(setPriors)
  }

  useEffect(() => {
    if (clientId) reload()
  }, [clientId])

  return (
    <div className="space-y-4">
      <Card title="Prior-year ingest & questionnaire">
        <div className="space-y-2 text-sm">
          {priors.map((p) => (
            <div key={p.tax_year} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
              TY{p.tax_year} · net {formatMoney(p.payload.net_income || 0)} · liability{' '}
              {formatMoney(p.payload.tax_liability || 0)}
              <div className="text-xs text-slate-500">forms: {(p.payload.forms || []).map((f: any) => f.type || f).join(', ')}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Document checklist & AI doc sorter (simulated)">
        <input
          type="file"
          multiple
          className="mb-3"
          onChange={async (e) => {
            if (!e.target.files?.length) return
            const res = await uploadTaxDocs(clientId, e.target.files, 2025)
            setMsg(res.results.map((r: any) => `${r.filename} → ${r.detected_type || 'unknown'}`).join('; '))
            setChecklist(res.checklist)
          }}
        />
        {msg && <div className="mb-2 text-xs text-emerald-600">{msg}</div>}
        <ul className="space-y-1 text-sm">
          {checklist.map((c) => (
            <li key={c.id} className="flex items-center gap-2">
              <span className={c.received ? 'text-emerald-500' : 'text-slate-400'}>{c.received ? '✓' : '○'}</span>
              {c.label} <span className="text-xs text-slate-500">({c.doc_type})</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card
        title="Book-to-tax mapping"
        action={
          <button
            type="button"
            className="text-xs text-emerald-600 hover:underline"
            onClick={() => downloadAuthFile(`/clients/${clientId}/tax/lead-sheet.xlsx`, `${clientId}-lead-sheet.xlsx`)}
          >
            Download lead sheet
          </button>
        }
      >
        {grid && (
          <>
            <div className="mb-2 text-xs text-amber-700 dark:text-amber-300">{grid.disclaimer}</div>
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-2 py-1 text-left">Line</th>
                    <th className="px-2 py-1 text-left">Description</th>
                    <th className="px-2 py-1 text-right">Book</th>
                    <th className="px-2 py-1 text-right">Adj</th>
                    <th className="px-2 py-1 text-right">Tax</th>
                    <th className="px-2 py-1 text-left">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {grid.lines.map((l: any) => (
                    <tr key={l.tax_line} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-2 py-1 font-mono text-xs">{l.tax_line}</td>
                      <td className="px-2 py-1">{l.description}</td>
                      <td className="px-2 py-1 text-right font-mono-amount">{formatMoney(l.book_amount)}</td>
                      <td className="px-2 py-1 text-right font-mono-amount">{formatMoney(l.adjustment)}</td>
                      <td className="px-2 py-1 text-right font-mono-amount">{formatMoney(l.tax_amount)}</td>
                      <td className="px-2 py-1 text-xs text-slate-500">{l.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
