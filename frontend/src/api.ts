import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export type Client = {
  id: string
  name: string
  entity_type: string
  beancount_path: string
  confidence_threshold: number
  close_date?: string | null
  ledger_ok?: boolean
  ledger_errors?: { file: string; line?: number; message: string }[]
}

export async function getClients() {
  const { data } = await api.get<Client[]>('/clients')
  return data
}

export async function getClient(id: string) {
  const { data } = await api.get<Client>(`/clients/${id}`)
  return data
}

export async function getTransactions(id: string, params?: Record<string, string>) {
  const { data } = await api.get(`/clients/${id}/transactions`, { params })
  return data
}

export async function getAccounts(id: string) {
  const { data } = await api.get(`/clients/${id}/accounts`)
  return data
}

export async function getTrialBalance(id: string) {
  const { data } = await api.get(`/clients/${id}/trial-balance`)
  return data
}

export async function getInbox(id: string) {
  const { data } = await api.get(`/clients/${id}/inbox`)
  return data
}

export async function previewImport(id: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post(`/clients/${id}/import/preview`, form)
  return data
}

export async function acceptImport(id: string, payload: unknown) {
  const { data } = await api.post(`/clients/${id}/import/accept`, payload)
  return data
}

export async function sendToInbox(id: string, rows: unknown[]) {
  const { data } = await api.post(`/clients/${id}/import/to-inbox`, { rows })
  return data
}

export async function acceptInbox(id: string, itemId: number, payload: unknown) {
  const { data } = await api.post(`/clients/${id}/inbox/${itemId}/accept`, payload)
  return data
}

export async function getPayees(id: string) {
  const { data } = await api.get(`/clients/${id}/close/payees`)
  return data
}

export async function getAnomalies(id: string) {
  const { data } = await api.get(`/clients/${id}/close/anomalies`)
  return data
}

export async function flagNeedsInfo(id: string, payload: unknown) {
  const { data } = await api.post(`/clients/${id}/close/needs-info`, payload)
  return data
}

export async function getCloseChecklist(id: string, periodEnd: string) {
  const { data } = await api.get(`/clients/${id}/close/checklist`, { params: { period_end: periodEnd } })
  return data
}

export async function closeMonth(id: string, periodEnd: string, force = false) {
  const { data } = await api.post(`/clients/${id}/close/month`, { period_end: periodEnd, force })
  return data
}

export async function getAccruals(id: string) {
  const { data } = await api.get(`/clients/${id}/close/accruals`)
  return data
}

export async function approveAccrual(id: string, payload: unknown) {
  const { data } = await api.post(`/clients/${id}/close/accruals/approve`, payload)
  return data
}

export async function createToken(id: string, label?: string) {
  const { data } = await api.post(`/clients/${id}/portal/tokens`, { label, days: 7 })
  return data
}

export async function listTokens(id: string) {
  const { data } = await api.get(`/clients/${id}/portal/tokens`)
  return data
}

export async function revokeToken(id: string, tokenId: number) {
  const { data } = await api.post(`/clients/${id}/portal/tokens/${tokenId}/revoke`)
  return data
}

export async function listStaged(id: string) {
  const { data } = await api.get(`/clients/${id}/portal/staged`)
  return data
}

export async function approveStaged(id: string, editId: number, payload: unknown = {}) {
  const { data } = await api.post(`/clients/${id}/portal/staged/${editId}/approve`, payload)
  return data
}

export async function getPortal(token: string) {
  const { data } = await api.get(`/portal/${token}`)
  return data
}

export async function submitPortal(token: string, payload: unknown) {
  const { data } = await api.post(`/portal/${token}/submit`, payload)
  return data
}

export async function uploadPortal(token: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post(`/portal/${token}/upload`, form)
  return data
}

export async function getBookToTax(id: string) {
  const { data } = await api.get(`/clients/${id}/tax/book-to-tax`)
  return data
}

export async function getChecklist(id: string, taxYear = 2025) {
  const { data } = await api.get(`/clients/${id}/tax/checklist`, { params: { tax_year: taxYear } })
  return data
}

export async function uploadTaxDocs(id: string, files: FileList, taxYear = 2025) {
  const form = new FormData()
  Array.from(files).forEach((f) => form.append('files', f))
  const { data } = await api.post(`/clients/${id}/tax/docs?tax_year=${taxYear}`, form)
  return data
}

export async function getPriorYears(id: string) {
  const { data } = await api.get(`/clients/${id}/tax/prior-years`)
  return data
}

export async function reasonableComp(id: string, payload: unknown) {
  const { data } = await api.post(`/clients/${id}/advisory/reasonable-comp`, payload)
  return data
}

export async function taxSavings(id: string, payload: unknown) {
  const { data } = await api.post(`/clients/${id}/advisory/savings`, payload)
  return data
}

export async function getIndustries() {
  const { data } = await api.get('/advisory/industries')
  return data
}

export default api
