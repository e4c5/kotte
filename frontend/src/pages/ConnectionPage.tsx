import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'
import { useAuthStore } from '../stores/authStore'
import SavedConnections from '../components/SavedConnections'
import type { ConnectionConfig } from '../services/session'

export default function ConnectionPage() {
  const navigate = useNavigate()
  const { connect, loading, error } = useSessionStore()
  const { authenticated, checkAuth } = useAuthStore()

  const [config, setConfig] = useState<ConnectionConfig>({
    host: 'localhost',
    port: 5432,
    database: 'postgres',
    user: 'postgres',
    password: '',
    sslmode: undefined,
  })
  const [connectionTested, setConnectionTested] = useState(false)
  const [testSuccessMessage, setTestSuccessMessage] = useState<string | null>(null)

  // Check authentication on mount
  useEffect(() => {
    checkAuth().then(() => {
      if (!authenticated) {
        navigate('/login')
      }
    })
  }, [authenticated, navigate, checkAuth])

  // Reset tested state when config changes
  useEffect(() => {
    setConnectionTested(false)
    setTestSuccessMessage(null)
  }, [config.host, config.port, config.database, config.user, config.password])

  // Redirect if not authenticated
  if (!authenticated) {
    return null
  }

  const handleTestConnection = async (e: React.FormEvent) => {
    e.preventDefault()
    setTestSuccessMessage(null)
    try {
      await connect(config)
      setConnectionTested(true)
      setTestSuccessMessage('Connection successful! You can save this connection or go to the workspace.')
    } catch {
      // Error is handled by store
    }
  }

  const handleGoToWorkspace = () => {
    navigate('/workspace')
  }

  const handleLoadConnection = (loadedConfig: ConnectionConfig) => {
    setConfig(loadedConfig)
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h2>Connect to Database</h2>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginTop: '2rem' }}>
        {/* Connection Form */}
        <div>
          <h3>New Connection</h3>
          <form onSubmit={handleTestConnection}>
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
            {testSuccessMessage && (
              <div style={{ color: 'green', marginBottom: '1rem' }}>{testSuccessMessage}</div>
            )}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: '0.75rem 1.5rem',
                  fontSize: '1rem',
                  cursor: loading ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? 'Testing...' : 'Test Connection'}
              </button>
              {connectionTested && (
                <button
                  type="button"
                  onClick={handleGoToWorkspace}
                  style={{
                    padding: '0.75rem 1.5rem',
                    fontSize: '1rem',
                    cursor: 'pointer',
                    backgroundColor: '#0d6efd',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                  }}
                >
                  Go to Workspace
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Saved Connections */}
        <div>
          <SavedConnections
            onLoadConnection={handleLoadConnection}
            currentConfig={config}
            connectionTested={connectionTested}
          />
        </div>
      </div>
    </div>
  )
}

