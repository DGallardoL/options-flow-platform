import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useAPI } from '../hooks/useAPI'
import { fetchPutCallRatio } from '../lib/api'

const COLORS = {
  Technology: '#06b6d4',
  Semiconductors: '#a78bfa',
  'Consumer Discretionary': '#f59e0b',
  Index: '#22c55e',
  Unknown: '#64748b',
}

export default function PutCallRatio() {
  const { data, loading, error } = useAPI(() => fetchPutCallRatio(), [])

  // Transform: group by hour, one series per sector
  const byHour = {}
  const sectors = new Set()
  for (const d of data?.data || []) {
    const hour = d._id?.hour ?? 0
    const sector = d._id?.sector ?? 'Unknown'
    sectors.add(sector)
    if (!byHour[hour]) byHour[hour] = { hour: `${hour}:00` }
    byHour[hour][sector] = d.put_call_ratio?.toFixed(2) || 0
  }
  const chartData = Object.values(byHour).sort((a, b) => parseInt(a.hour) - parseInt(b.hour))

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Put/Call Ratio by Sector</h2>

      {loading && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={400}>
          <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="hour" stroke="var(--text-muted)" fontSize={12} />
            <YAxis stroke="var(--text-muted)" fontSize={12} />
            <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, fontFamily: 'JetBrains Mono' }} />
            <ReferenceLine y={1} stroke="var(--amber)" strokeDasharray="5 5" label={{ value: 'P/C = 1.0', fill: 'var(--amber)', fontSize: 11 }} />
            {[...sectors].map(sector => (
              <Area
                key={sector}
                type="monotone"
                dataKey={sector}
                stroke={COLORS[sector] || '#64748b'}
                fill={COLORS[sector] || '#64748b'}
                fillOpacity={0.1}
                strokeWidth={2}
                name={sector}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        !loading && <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>No put/call ratio data available</div>
      )}

      <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
        {[...sectors].map(s => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: COLORS[s] || '#64748b' }} />
            <span style={{ color: 'var(--text-muted)' }}>{s}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
