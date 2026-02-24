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

  const inputClass =
    'w-full px-3 py-2 text-sm bg-zinc-800 border border-zinc-600 rounded-lg text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
  const labelClass = 'block text-sm font-medium text-zinc-300 mb-1'

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold text-zinc-100 mb-6">Connect to Database</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Connection Form */}
        <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-6">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide mb-4">
            New Connection
          </h3>
          <form onSubmit={handleTestConnection} className="space-y-4">
            <div>
              <label htmlFor="conn-host" className={labelClass}>
                Host
              </label>
              <input
                id="conn-host"
                type="text"
                value={config.host}
                onChange={(e) => setConfig({ ...config, host: e.target.value })}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="conn-port" className={labelClass}>
                Port
              </label>
              <input
                id="conn-port"
                type="number"
                value={config.port}
                onChange={(e) => {
                  const next = parseInt(e.target.value, 10)
                  setConfig({ ...config, port: Number.isFinite(next) ? next : config.port })
                }}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="conn-database" className={labelClass}>
                Database
              </label>
              <input
                id="conn-database"
                type="text"
                value={config.database}
                onChange={(e) => setConfig({ ...config, database: e.target.value })}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="conn-user" className={labelClass}>
                User
              </label>
              <input
                id="conn-user"
                type="text"
                value={config.user}
                onChange={(e) => setConfig({ ...config, user: e.target.value })}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="conn-password" className={labelClass}>
                Password
              </label>
              <input
                id="conn-password"
                type="password"
                value={config.password}
                onChange={(e) => setConfig({ ...config, password: e.target.value })}
                required
                className={inputClass}
              />
            </div>
            {error && (
              <div className="text-sm text-red-400 bg-red-900/30 border border-red-800 rounded-lg px-3 py-2">
                {error}
              </div>
            )}
            {testSuccessMessage && (
              <div className="text-sm text-emerald-400 bg-emerald-900/30 border border-emerald-800 rounded-lg px-3 py-2">
                {testSuccessMessage}
              </div>
            )}
            <div className="flex flex-wrap gap-3 pt-1">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Testing…' : 'Test Connection'}
              </button>
              {connectionTested && (
                <button
                  type="button"
                  onClick={handleGoToWorkspace}
                  className="px-4 py-2 text-sm font-medium rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
                >
                  Go to Workspace
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Saved Connections */}
        <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-6">
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

