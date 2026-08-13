import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components'
import { AdvisoryPage } from './pages/AdvisoryPage'
import { ClientPortalPage } from './pages/ClientPortalPage'
import { ClosePage } from './pages/ClosePage'
import { ImportPage } from './pages/ImportPage'
import { InboxPage } from './pages/InboxPage'
import { LedgerPage } from './pages/LedgerPage'
import { PortalAdminPage } from './pages/PortalAdminPage'
import { TaxPage } from './pages/TaxPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/portal/:token" element={<ClientPortalPage />} />
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
      </Routes>
    </BrowserRouter>
  )
}
