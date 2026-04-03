import { useState } from 'react'
import { Activity, TrendingUp, BarChart3, Gauge, GitBranch, Server, ArrowLeftRight } from 'lucide-react'
import FlowScanner from './components/FlowScanner'
import IVSkewChart from './components/IVSkewChart'
import PutCallRatio from './components/PutCallRatio'
import GammaExposure from './components/GammaExposure'
import SpreadAnalysis from './components/SpreadAnalysis'
import DataLineage from './components/DataLineage'
import SystemStatus from './components/SystemStatus'

const TABS = [
  { id: 'flow', label: 'Flow', icon: Activity },
  { id: 'iv-skew', label: 'IV Skew', icon: TrendingUp },
  { id: 'pc-ratio', label: 'P/C', icon: BarChart3 },
  { id: 'gamma', label: 'Gamma', icon: Gauge },
  { id: 'spread', label: 'Spread', icon: ArrowLeftRight },
  { id: 'lineage', label: 'Lineage', icon: GitBranch },
  { id: 'status', label: 'Status', icon: Server },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('flow')

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: 'var(--cyan)', fontSize: 20, fontWeight: 700 }}>OPTIONS</span>
          <span style={{ color: 'var(--text-muted)', fontSize: 20 }}>FLOW</span>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            marginLeft: 16, padding: '4px 10px',
            background: 'rgba(34,197,94,0.1)',
            border: '1px solid rgba(34,197,94,0.3)',
            borderRadius: 4,
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--green)',
              animation: 'pulse 2s infinite',
            }} />
            <span style={{ color: 'var(--green)', fontSize: 11 }}>LIVE</span>
          </div>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          Options Flow Intelligence Platform
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1 }}>
        {/* Sidebar */}
        <nav style={{
          width: 180,
          background: 'var(--surface)',
          borderRight: '1px solid var(--border)',
          padding: '16px 0',
          flexShrink: 0,
        }}>
          {TABS.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: '10px 20px',
                  border: 'none',
                  background: isActive ? 'rgba(6,182,212,0.1)' : 'transparent',
                  color: isActive ? 'var(--cyan)' : 'var(--text-muted)',
                  borderLeft: isActive ? '2px solid var(--cyan)' : '2px solid transparent',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontFamily: 'inherit',
                  transition: 'all 0.15s',
                }}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </nav>

        {/* Content */}
        <main style={{ flex: 1, padding: 24, overflow: 'auto' }}>
          {activeTab === 'flow' && <FlowScanner />}
          {activeTab === 'iv-skew' && <IVSkewChart />}
          {activeTab === 'pc-ratio' && <PutCallRatio />}
          {activeTab === 'gamma' && <GammaExposure />}
          {activeTab === 'spread' && <SpreadAnalysis />}
          {activeTab === 'lineage' && <DataLineage />}
          {activeTab === 'status' && <SystemStatus />}
        </main>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}
