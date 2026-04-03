import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useAPI } from '../hooks/useAPI'
import { fetchGammaExposure } from '../lib/api'

export default function GammaExposure() {
  const { data, loading, error } = useAPI(() => fetchGammaExposure(), [])

  const chartData = (data?.data || []).map(d => ({
    ticker: d._id || 'Unknown',
    call: d.call_gamma_m?.toFixed(2) || 0,
    put: d.put_gamma_m?.toFixed(2) || 0,
    net: d.net_gamma_m?.toFixed(2) || 0,
  }))

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Gamma Exposure ($M)</h2>

      {loading && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 20, right: 30, left: 60, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis type="number" stroke="var(--text-muted)" fontSize={12} />
            <YAxis type="category" dataKey="ticker" stroke="var(--text-muted)" fontSize={12} width={50} />
            <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, fontFamily: 'JetBrains Mono' }} />
            <Bar dataKey="call" name="Call GEX" fill="var(--green)" radius={[0, 4, 4, 0]} />
            <Bar dataKey="put" name="Put GEX" fill="var(--red)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        !loading && <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>No gamma exposure data</div>
      )}

      <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--green)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Call GEX</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--red)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Put GEX</span>
        </div>
      </div>
    </div>
  )
}
