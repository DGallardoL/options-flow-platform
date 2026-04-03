import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useAPI } from '../hooks/useAPI'
import { fetchIVSkew } from '../lib/api'

const TICKERS = ['AAPL', 'NVDA', 'TSLA', 'SPY', 'AMZN', 'META', 'MSFT', 'GOOGL', 'QQQ', 'AMD']
const BUCKET_ORDER = ['P50', 'P25', 'P10', 'ATM', 'C10', 'C25', 'C50']

export default function IVSkewChart() {
  const [underlying, setUnderlying] = useState('AAPL')
  const { data, loading, error } = useAPI(() => fetchIVSkew(underlying), [underlying])

  const chartData = BUCKET_ORDER.map(bucket => {
    const point = (data?.data || []).find(d => d._id === bucket)
    return {
      bucket,
      iv: point ? (point.avg_iv * 100).toFixed(2) : null,
      count: point?.count || 0,
    }
  }).filter(d => d.iv !== null)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>IV Skew</h2>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TICKERS.map(t => (
            <button
              key={t}
              onClick={() => setUnderlying(t)}
              style={{
                padding: '3px 8px', fontSize: 11, borderRadius: 3, cursor: 'pointer',
                fontFamily: 'inherit',
                border: '1px solid',
                borderColor: underlying === t ? 'var(--cyan)' : 'var(--border)',
                background: underlying === t ? 'rgba(6,182,212,0.1)' : 'transparent',
                color: underlying === t ? 'var(--cyan)' : 'var(--text-muted)',
              }}
            >{t}</button>
          ))}
        </div>
      </div>

      {loading && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="bucket" stroke="var(--text-muted)" fontSize={12} />
            <YAxis stroke="var(--text-muted)" fontSize={12} label={{ value: 'IV %', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)' }} />
            <Tooltip
              contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, fontFamily: 'JetBrains Mono' }}
              labelStyle={{ color: 'var(--text)' }}
            />
            <Line type="monotone" dataKey="iv" stroke="var(--cyan)" strokeWidth={2} dot={{ fill: 'var(--cyan)', r: 4 }} name="IV %" />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        !loading && <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>No IV skew data for {underlying}</div>
      )}
    </div>
  )
}
