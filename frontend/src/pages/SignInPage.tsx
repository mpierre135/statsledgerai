import { SignIn } from '@clerk/react'
import { dark } from '@clerk/themes'
import { Link, useSearchParams } from 'react-router-dom'
import { ALLOWED_EMAIL } from '../auth'

const appearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: '#10b981',
    colorBackground: '#0f172a',
    colorInputBackground: '#1e293b',
    colorNeutral: '#94a3b8',
    colorText: '#f8fafc',
    borderRadius: '0.75rem',
  },
}

export function SignInPage() {
  const [params] = useSearchParams()
  const forbidden = params.get('error') === 'forbidden'

  return (
    <div className="flex min-h-full items-center justify-center bg-[#0F172A] px-4 py-12 text-slate-50">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500 text-lg font-bold text-white">
            SL
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">StatsLedger AI</h1>
          <p className="mt-1 text-sm text-slate-400">Firm workspace · sign in to continue</p>
        </div>
        {forbidden ? (
          <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-center text-sm text-amber-200">
            This workspace is limited to {ALLOWED_EMAIL}.
          </p>
        ) : (
          <p className="text-center text-xs text-slate-500">Access is restricted to {ALLOWED_EMAIL}.</p>
        )}
        <div className="flex justify-center">
          <SignIn
            routing="path"
            path="/sign-in"
            signUpUrl="/sign-up"
            fallbackRedirectUrl="/"
            appearance={appearance}
          />
        </div>
        <p className="text-center text-xs text-slate-500">
          First time?{' '}
          <Link to="/sign-up" className="text-emerald-400 hover:underline">
            Create the firm account
          </Link>
        </p>
      </div>
    </div>
  )
}
