import { useAuth, useClerk, useUser } from '@clerk/react'
import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { isAllowedUser } from './auth'

export function ProtectedRoute() {
  const { isLoaded, isSignedIn } = useAuth()
  const { user } = useUser()
  const { signOut } = useClerk()

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !user) return
    if (!isAllowedUser(user)) {
      void signOut({ redirectUrl: '/sign-in?error=forbidden' })
    }
  }, [isLoaded, isSignedIn, signOut, user])

  if (!isLoaded) {
    return (
      <div className="flex min-h-full items-center justify-center bg-[#0F172A] text-slate-400">
        Loading workspace…
      </div>
    )
  }
  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />
  }
  if (user && !isAllowedUser(user)) {
    return (
      <div className="flex min-h-full items-center justify-center bg-[#0F172A] text-slate-400">
        Checking access…
      </div>
    )
  }
  return <Outlet />
}
