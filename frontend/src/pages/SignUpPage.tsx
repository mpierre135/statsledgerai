import { SignUp } from '@clerk/react'
import { dark } from '@clerk/themes'
import { Link } from 'react-router-dom'
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

export function SignUpPage() {
  return (
    <div className="flex min-h-full items-center justify-center bg-[#0F172A] px-4 py-12 text-slate-50">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500 text-lg font-bold text-white">
            SL
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Create firm access</h1>
          <p className="mt-1 text-sm text-slate-400">Only {ALLOWED_EMAIL} can register.</p>
        </div>
        <div className="flex justify-center">
          <SignUp
            routing="path"
            path="/sign-up"
            signInUrl="/sign-in"
            fallbackRedirectUrl="/"
            appearance={appearance}
          />
        </div>
        <p className="text-center text-xs text-slate-500">
          Already have access?{' '}
          <Link to="/sign-in" className="text-emerald-400 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
