import { useAuth } from '@clerk/react'
import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { setAuthTokenGetter } from './api'
import { AppShell } from './components'
import { ProtectedRoute } from './ProtectedRoute'
import { AdvisoryPage } from './pages/AdvisoryPage'
import { ClientPortalPage } from './pages/ClientPortalPage'
import { ClosePage } from './pages/ClosePage'
import { ImportPage } from './pages/ImportPage'
import { InboxPage } from './pages/InboxPage'
import { LedgerPage } from './pages/LedgerPage'
import { PortalAdminPage } from './pages/PortalAdminPage'
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'
import { TaxPage } from './pages/TaxPage'

function ClerkTokenBridge() {
  const { getToken, isSignedIn } = useAuth()
  useEffect(() => {
    setAuthTokenGetter(async () => (isSignedIn ? getToken() : null))
    return () => setAuthTokenGetter(null)
  }, [getToken, isSignedIn])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <ClerkTokenBridge />
      <Routes>
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route path="/sign-up/*" element={<SignUpPage />} />
        <Route path="/portal/:token" element={<ClientPortalPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Navigate to="/c/harbor_lemon" replace />} />
          <Route path="/c/:clientId" element={<AppShell />}>
            <Route index element={<LedgerPage />} />
            <Route path="import" element={<ImportPage />} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="close" element={<ClosePage />} />
            <Route path="portal" element={<PortalAdminPage />} />
            <Route path="tax" element={<TaxPage />} />
            <Route path="advisory" element={<AdvisoryPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
