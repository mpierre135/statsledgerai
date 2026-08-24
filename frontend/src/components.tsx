import { UserButton } from '@clerk/react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import {
  BookOpen,
  Calculator,
  CheckSquare,
  LayoutDashboard,
  Link2,
  Moon,
  Sun,
  Upload,
  Wallet,
} from 'lucide-react'
import { getClient, getClients, type Client } from './api'

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    if (typeof window === 'undefined') return true
    return localStorage.getItem('theme') !== 'light'
  })
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  return { dark, toggle: () => setDark((d) => !d) }
}

export function AppShell() {
  const { dark, toggle } = useDarkMode()
  const [clients, setClients] = useState<Client[]>([])
  const { clientId } = useParams()
  const navigate = useNavigate()

  useEffect(() => {
    getClients().then((c) => {
      setClients(c)
      if (!clientId && c[0]) navigate(`/c/${c[0].id}`, { replace: true })
    })
  }, [clientId, navigate])

  const nav = [
    { to: '', end: true, label: 'Ledger', icon: BookOpen },
    { to: 'import', label: 'Import', icon: Upload },
    { to: 'inbox', label: 'Review Inbox', icon: CheckSquare },
    { to: 'close', label: 'Close & QA', icon: LayoutDashboard },
    { to: 'portal', label: 'Client Portal', icon: Link2 },
    { to: 'tax', label: 'Tax Prep', icon: Wallet },
    { to: 'advisory', label: 'Advisory', icon: Calculator },
  ]

  return (
    <div className="min-h-full bg-slate-50 text-slate-900 dark:bg-[#0F172A] dark:text-slate-50">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-[#1E293B]/80">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-sm font-bold text-white">
                SL
              </div>
              <div>
                <div className="text-sm font-semibold tracking-tight">StatsLedger AI</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">Flat-file books · mint-grade close</div>
              </div>
            </Link>
            <select
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              value={clientId || ''}
              onChange={(e) => navigate(`/c/${e.target.value}`)}
            >
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.entity_type})
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={toggle}
              className="rounded-lg border border-slate-200 p-2 transition hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
              aria-label="Toggle theme"
            >
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <UserButton />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 px-6 py-6 lg:grid-cols-[220px_1fr]">
        <nav className="space-y-1">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={label}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition ${
                  isActive
                    ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function Card({
  title,
  children,
  action,
}: {
  title?: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-[#1E293B]">
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title ? <h2 className="text-sm font-semibold tracking-tight">{title}</h2> : <div />}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-[#1E293B]">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-1 font-mono-amount text-2xl font-semibold text-emerald-600 dark:text-emerald-400">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
    </div>
  )
}

export function LedgerBanner({ clientId }: { clientId: string }) {
  const [errors, setErrors] = useState<Client['ledger_errors']>([])
  useEffect(() => {
    getClient(clientId).then((c) => setErrors(c.ledger_ok ? [] : c.ledger_errors || []))
  }, [clientId])
  if (!errors?.length) return null
  return (
    <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-200">
      <div className="font-semibold">Ledger has errors — writes blocked until fixed</div>
      <ul className="mt-2 space-y-1 font-mono text-xs">
        {errors.map((e, i) => (
          <li key={i}>
            {e.file}:{e.line ?? '?'} — {e.message}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function formatMoney(v: string | number) {
  const n = Number(v)
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
}
