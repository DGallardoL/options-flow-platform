import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { fetchFlowScanner } from '../lib/api'

const FILTERS = ['All', 'Unusual', 'Bullish', 'Bearish']

export default function FlowScanner() {
  const [filter, setFilter] = useState('All')
  const { data, loading, error } = useAPI(() => fetchFlowScanner(200), [], 5000)

  const trades = (data?.data || []).filter(t => {
    if (filter === 'Unusual') return t.unusual_flag
    if (filter === 'Bullish') return t.sentiment === 'Bullish'
    if (filter === 'Bearish') return t.sentiment === 'Bearish'
    return true
  })

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>Flow Scanner</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '4px 12px',
                fontSize: 12,
                border: '1px solid',
                borderColor: filter === f ? 'var(--cyan)' : 'var(--border)',
                background: filter === f ? 'rgba(6,182,212,0.1)' : 'transparent',
                color: filter === f ? 'var(--cyan)' : 'var(--text-muted)',
                borderRadius: 4,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >{f}</button>
          ))}
        </div>
      </div>

      {loading && !data && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Time', 'Symbol', 'Type', 'Strike', 'Price', 'Size', 'Dollar Vol', 'IV', 'Sentiment', 'Sector'].map(h => (
                <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 500 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.slice(0, 100).map((t, i) => (
              <tr
                key={i}
                style={{
                  borderBottom: '1px solid var(--border)',
                  background: t.unusual_flag ? 'rgba(245,158,11,0.05)' : 'transparent',
                }}
              >
                <td style={{ padding: '6px 12px', color: 'var(--text-muted)' }}>
                  {t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '-'}
                </td>
                <td style={{ padding: '6px 12px', fontWeight: 500 }}>{t.underlying || '-'}</td>
                <td style={{ padding: '6px 12px' }}>
                  <span style={{
                    padding: '2px 6px',
                    borderRadius: 3,
                    fontSize: 11,
                    background: t.contract_type === 'call' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                    color: t.contract_type === 'call' ? 'var(--green)' : 'var(--red)',
                  }}>
                    {t.contract_type?.toUpperCase() || '-'}
                  </span>
                </td>
                <td style={{ padding: '6px 12px' }}>${t.strike?.toFixed(0) || '-'}</td>
                <td style={{ padding: '6px 12px' }}>${t.price?.toFixed(2) || '-'}</td>
                <td style={{ padding: '6px 12px' }}>{t.size || '-'}</td>
                <td style={{ padding: '6px 12px', color: 'var(--cyan)' }}>
                  ${t.dollar_volume ? (t.dollar_volume / 1000).toFixed(1) + 'K' : '-'}
                </td>
                <td style={{ padding: '6px 12px' }}>
                  {t.implied_volatility ? (t.implied_volatility * 100).toFixed(1) + '%' : '-'}
                </td>
                <td style={{ padding: '6px 12px' }}>
                  <span style={{
                    padding: '2px 6px', borderRadius: 3, fontSize: 11,
                    background: t.sentiment === 'Bullish' ? 'rgba(34,197,94,0.15)'
                      : t.sentiment === 'Bearish' ? 'rgba(239,68,68,0.15)' : 'rgba(100,116,139,0.15)',
                    color: t.sentiment === 'Bullish' ? 'var(--green)'
                      : t.sentiment === 'Bearish' ? 'var(--red)' : 'var(--text-muted)',
                  }}>
                    {t.sentiment || '-'}
                  </span>
                </td>
                <td style={{ padding: '6px 12px', color: 'var(--purple)' }}>{t.sector || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 11 }}>
        Showing {trades.length} trades {filter !== 'All' ? `(${filter})` : ''} · Auto-refresh 5s
      </div>
    </div>
  )
}
