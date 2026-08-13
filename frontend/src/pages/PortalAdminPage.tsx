import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card } from '../components'
import { approveStaged, createToken, listStaged, listTokens, revokeToken } from '../api'

export function PortalAdminPage() {
  const { clientId = '' } = useParams()
  const [tokens, setTokens] = useState<any[]>([])
  const [staged, setStaged] = useState<any[]>([])
  const [freshLink, setFreshLink] = useState('')
  const [msg, setMsg] = useState('')

  const reload = () => {
    listTokens(clientId).then(setTokens)
    listStaged(clientId).then(setStaged)
  }

  useEffect(() => {
    if (clientId) reload()
  }, [clientId])

  return (
    <div className="space-y-4">
      <Card title="Magic-link portal">
        <p className="mb-3 text-sm text-slate-500">
          Issue a passwordless link scoped to this client. Tokens are stored hashed; revoke anytime.
        </p>
        <button
          className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white"
          onClick={async () => {
            const res = await createToken(clientId, 'Client review')
            const url = `${window.location.origin}${res.link_path}`
            setFreshLink(url)
            setMsg('Link created — copy it now; the raw token is only shown once.')
            reload()
          }}
        >
          Generate magic link
        </button>
        {freshLink && (
          <div className="mt-3 break-all rounded-lg bg-slate-100 p-3 font-mono text-xs dark:bg-slate-900">{freshLink}</div>
        )}
        {msg && <div className="mt-2 text-sm text-emerald-600">{msg}</div>}

        <div className="mt-4 space-y-2">
          {tokens.map((t) => (
            <div key={t.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
              <div>
                <div>{t.label || `Token #${t.id}`}</div>
                <div className="text-xs text-slate-500">
                  expires {t.expires_at}
                  {t.revoked_at ? ' · REVOKED' : ''}
                </div>
              </div>
              {!t.revoked_at && (
                <button
                  className="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600"
                  onClick={async () => {
                    await revokeToken(clientId, t.id)
                    reload()
                  }}
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card title="Staged client edits (approve → ledger)">
        {!staged.length && <div className="text-sm text-slate-500">No pending client submissions.</div>}
        {staged.map((s) => (
          <div key={s.id} className="mb-3 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
            <div>#{s.id} · category: {s.suggested_category || '—'} · memo: {s.memo || '—'}</div>
            <div className="text-xs text-slate-500">
              inbox:{s.inbox_id ?? '—'} needs_info:{s.needs_info_id ?? '—'} receipt:{s.receipt_path || '—'}
            </div>
            <button
              className="mt-2 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs text-white"
              onClick={async () => {
                await approveStaged(clientId, s.id)
                setMsg(`Approved staged edit #${s.id}`)
                reload()
              }}
            >
              Approve into ledger
            </button>
          </div>
        ))}
      </Card>
    </div>
  )
}
