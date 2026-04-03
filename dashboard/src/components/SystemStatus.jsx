import { Activity, Database, Cpu, BarChart3 } from 'lucide-react'
import { useAPI } from '../hooks/useAPI'
import { fetchHealth } from '../lib/api'

function StatCard({ label, value, icon: Icon, color, status }) {
  return (
    <div style={{
      padding: 20, background: 'var(--surface)',
      border: '1px solid var(--border)', borderRadius: 6,
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
        <Icon size={16} style={{ color }} />
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      {status && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: status === 'ok' ? 'var(--green)' : 'var(--red)',
          }} />
          <span style={{ fontSize: 11, color: status === 'ok' ? 'var(--green)' : 'var(--red)' }}>
            {status === 'ok' ? 'Connected' : 'Error'}
          </span>
        </div>
      )}
    </div>
  )
}

export default function SystemStatus() {
  const { data, loading, error } = useAPI(() => fetchHealth(), [], 10000)

  const counts = data?.counts || {}
  const isHealthy = data?.status === 'healthy'

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>System Status</h2>

      {loading && !data && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)', marginBottom: 16 }}>API Error: {error}</div>}

      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 16, marginBottom: 24,
      }}>
        <StatCard
          label="MongoDB"
          value={isHealthy ? 'Online' : 'Offline'}
          icon={Database}
          color={isHealthy ? 'var(--green)' : 'var(--red)'}
          status={isHealthy ? 'ok' : 'error'}
        />
        <StatCard
          label="Raw Trades"
          value={counts.raw_trades?.toLocaleString() || '0'}
          icon={Activity}
          color="var(--cyan)"
        />
        <StatCard
          label="Enriched Trades"
          value={counts.enriched_trades?.toLocaleString() || '0'}
          icon={Cpu}
          color="var(--purple)"
        />
        <StatCard
          label="Aggregated Metrics"
          value={counts.aggregated_metrics?.toLocaleString() || '0'}
          icon={BarChart3}
          color="var(--amber)"
        />
      </div>

      <div style={{
        padding: 16, background: 'var(--surface)',
        border: '1px solid var(--border)', borderRadius: 6,
      }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Pipeline Status</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { stage: 'WebSocket Ingestion', status: counts.raw_trades > 0 },
            { stage: 'REST Poller (Snapshots)', status: counts.raw_trades > 0 },
            { stage: 'Spark Clean Job', status: counts.enriched_trades > 0 },
            { stage: 'Spark Enrich Job', status: counts.enriched_trades > 0 },
            { stage: 'Spark Transform Job', status: counts.aggregated_metrics > 0 },
            { stage: 'API Server', status: isHealthy },
          ].map(({ stage, status }) => (
            <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: status ? 'var(--green)' : 'var(--red)',
              }} />
              <span style={{ fontSize: 12, color: status ? 'var(--text)' : 'var(--text-muted)' }}>{stage}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 11 }}>
        Auto-refresh every 10s
      </div>
    </div>
  )
}
