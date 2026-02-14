import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'
import type { ConnectionConfig } from '../services/session'

export default function ConnectionPage() {
  const navigate = useNavigate()
  const { connect, loading, error } = useSessionStore()
  const [config, setConfig] = useState<ConnectionConfig>({
    host: 'localhost',
    port: 5432,
    database: 'postgres',
    user: 'postgres',
    password: '',
    sslmode: undefined,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await connect(config)
      navigate('/workspace')
    } catch (err) {
      // Error is handled by store
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h2>Connect to Database</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label>
            Host:
            <input
              type="text"
              value={config.host}
              onChange={(e) => setConfig({ ...config, host: e.target.value })}
              required
              style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
            />
          </label>
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label>
            Port:
            <input
              type="number"
              value={config.port}
              onChange={(e) => setConfig({ ...config, port: parseInt(e.target.value) })}
              required
              style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
            />
          </label>
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label>
            Database:
            <input
              type="text"
              value={config.database}
              onChange={(e) => setConfig({ ...config, database: e.target.value })}
              required
              style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
            />
          </label>
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label>
            User:
            <input
              type="text"
              value={config.user}
              onChange={(e) => setConfig({ ...config, user: e.target.value })}
              required
              style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
            />
          </label>
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label>
            Password:
            <input
              type="password"
              value={config.password}
              onChange={(e) => setConfig({ ...config, password: e.target.value })}
              required
              style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
            />
          </label>
        </div>
        {error && (
          <div style={{ color: 'red', marginBottom: '1rem' }}>{error}</div>
        )}
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '0.75rem 1.5rem',
            fontSize: '1rem',
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Connecting...' : 'Connect'}
        </button>
      </form>
    </div>
  )
}

