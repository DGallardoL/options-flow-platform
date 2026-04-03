import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useAPI } from '../hooks/useAPI'
import { fetchSpreadMoneyness } from '../lib/api'

const BUCKET_ORDER = ['Deep ITM', 'ITM', 'ATM', 'OTM', 'Deep OTM']

export default function SpreadAnalysis() {
  const { data, loading, error } = useAPI(() => fetchSpreadMoneyness(), [])

  const chartData = BUCKET_ORDER.map(bucket => {
    const point = (data?.data || []).find(d => d._id === bucket)
    return {
      bucket,
      spread: point?.avg_spread?.toFixed(4) || 0,
      volume: point?.total_volume || 0,
    }
  })

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Spread vs Moneyness</h2>

      {loading && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}

      {(data?.data || []).length > 0 ? (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="bucket" stroke="var(--text-muted)" fontSize={12} />
            <YAxis yAxisId="left" stroke="var(--cyan)" fontSize={12} label={{ value: 'Spread', angle: -90, position: 'insideLeft', fill: 'var(--cyan)' }} />
            <YAxis yAxisId="right" orientation="right" stroke="var(--purple)" fontSize={12} label={{ value: 'Volume', angle: 90, position: 'insideRight', fill: 'var(--purple)' }} />
            <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, fontFamily: 'JetBrains Mono' }} />
            <Bar yAxisId="left" dataKey="spread" name="Avg Spread" fill="var(--cyan)" fillOpacity={0.6} radius={[4, 4, 0, 0]} />
            <Line yAxisId="right" type="monotone" dataKey="volume" name="Volume" stroke="var(--purple)" strokeWidth={2} dot={{ fill: 'var(--purple)', r: 4 }} />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        !loading && <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>No spread data available</div>
      )}
    </div>
  )
}
