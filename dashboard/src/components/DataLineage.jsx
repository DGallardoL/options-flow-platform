import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { useAPI } from '../hooks/useAPI'
import { fetchLineage } from '../lib/api'

const STAGES = [
  { key: 'raw_trade', label: 'Raw Trade', color: 'var(--red)' },
  { key: 'cleaned_trade', label: 'Cleaned', color: 'var(--amber)' },
  { key: 'enriched_trade', label: 'Enriched', color: 'var(--cyan)' },
  { key: 'aggregated_metric', label: 'Aggregated', color: 'var(--green)' },
]

export default function DataLineage() {
  const [sym, setSym] = useState('O:AAPL251219C00200000')
  const [inputSym, setInputSym] = useState(sym)
  const { data, loading, error } = useAPI(() => fetchLineage(sym), [sym])

  const handleSubmit = (e) => {
    e.preventDefault()
    setSym(inputSym)
  }

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Data Lineage</h2>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <input
          value={inputSym}
          onChange={e => setInputSym(e.target.value)}
          placeholder="O:AAPL251219C00200000"
          style={{
            flex: 1, padding: '8px 12px', fontSize: 13,
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 4, color: 'var(--text)', fontFamily: 'inherit',
            outline: 'none',
          }}
        />
        <button type="submit" style={{
          padding: '8px 16px', fontSize: 13, borderRadius: 4,
          background: 'rgba(6,182,212,0.15)', border: '1px solid var(--cyan)',
          color: 'var(--cyan)', cursor: 'pointer', fontFamily: 'inherit',
        }}>Trace</button>
      </form>

      {loading && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}
      {error && <div style={{ color: 'var(--red)' }}>Error: {error}</div>}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, overflowX: 'auto' }}>
        {STAGES.map((stage, i) => {
          const stageData = data?.data?.[stage.key]
          return (
            <div key={stage.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <div style={{
                minWidth: 240, padding: 16,
                background: 'var(--surface)', border: `1px solid ${stage.color}`,
                borderRadius: 6, borderTop: `3px solid ${stage.color}`,
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: stage.color, marginBottom: 12 }}>
                  {stage.label}
                </div>
                {stageData ? (
                  <pre style={{
                    fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all', maxHeight: 300, overflow: 'auto',
                  }}>
                    {JSON.stringify(stageData, null, 2)}
                  </pre>
                ) : (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No data</div>
                )}
              </div>
              {i < STAGES.length - 1 && (
                <div style={{ display: 'flex', alignItems: 'center', paddingTop: 40 }}>
                  <ArrowRight size={20} style={{ color: 'var(--text-muted)' }} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
