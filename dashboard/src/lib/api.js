import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

export const fetchFlowScanner = (limit = 100) =>
  api.get(`/flow/scanner?limit=${limit}`).then(r => r.data)

export const fetchUnusual = (date, limit = 50) => {
  const params = new URLSearchParams({ limit })
  if (date) params.set('date', date)
  return api.get(`/flow/unusual?${params}`).then(r => r.data)
}

export const fetchIVSkew = (underlying = 'AAPL', date) => {
  const params = new URLSearchParams({ underlying })
  if (date) params.set('date', date)
  return api.get(`/analytics/iv-skew?${params}`).then(r => r.data)
}

export const fetchPutCallRatio = (date) => {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  return api.get(`/analytics/put-call-ratio?${params}`).then(r => r.data)
}

export const fetchSpreadMoneyness = (date) => {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  return api.get(`/analytics/spread-moneyness?${params}`).then(r => r.data)
}

export const fetchGammaExposure = (date, limit = 20) => {
  const params = new URLSearchParams({ limit })
  if (date) params.set('date', date)
  return api.get(`/analytics/gamma-exposure?${params}`).then(r => r.data)
}

export const fetchLineage = (sym) =>
  api.get(`/analytics/lineage?sym=${encodeURIComponent(sym)}`).then(r => r.data)

export const fetchHealth = () =>
  api.get('/health').then(r => r.data)

export default api
