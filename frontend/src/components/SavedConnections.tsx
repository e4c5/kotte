/**
 * Component for displaying and managing saved database connections.
 */

import { useState, useEffect } from 'react'
import {
  saveConnection,
  listConnections,
  getConnection,
  deleteConnection,
  type SavedConnection,
} from '../services/connections'
import type { ConnectionConfig } from '../services/session'

interface SavedConnectionsProps {
  onLoadConnection: (config: ConnectionConfig) => void
  currentConfig?: ConnectionConfig
  connectionTested?: boolean
}

export default function SavedConnections({
  onLoadConnection,
  currentConfig,
  connectionTested = false,
}: SavedConnectionsProps) {
  const [connections, setConnections] = useState<SavedConnection[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [connectionName, setConnectionName] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadConnections()
  }, [])

  const loadConnections = async () => {
    setLoading(true)
    setError(null)
    try {
      const saved = await listConnections()
      setConnections(saved)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load connections')
    } finally {
      setLoading(false)
    }
  }

  const handleLoad = async (connectionId: string) => {
    try {
      const connection = await getConnection(connectionId)
      onLoadConnection({
        host: connection.host,
        port: connection.port,
        database: connection.database,
        user: connection.username,
        password: connection.password,
        sslmode: connection.sslmode,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load connection')
    }
  }

  const handleSave = async () => {
    if (!currentConfig || !connectionName.trim()) {
      setError('Please provide a connection name')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await saveConnection({
        name: connectionName.trim(),
        host: currentConfig.host,
        port: currentConfig.port,
        database: currentConfig.database,
        username: currentConfig.user,
        password: currentConfig.password,
        sslmode: currentConfig.sslmode,
      })
      setConnectionName('')
      setShowSaveDialog(false)
      await loadConnections()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save connection')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (connectionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this connection?')) {
      return
    }

    try {
      await deleteConnection(connectionId)
      await loadConnections()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete connection')
    }
  }

  const inputClass =
    'w-full px-3 py-2 text-sm bg-zinc-800 border border-zinc-600 rounded-lg text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'

  return (
    <div>
      <div className="flex flex-wrap justify-between items-center gap-2 mb-4">
        <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">
          Saved Connections
        </h3>
        {currentConfig && (
          <button
            type="button"
            onClick={() => connectionTested && setShowSaveDialog(true)}
            disabled={!connectionTested}
            title={
              !connectionTested ? 'Test the connection first to save it' : 'Save this connection'
            }
            className="px-3 py-1.5 text-sm rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Save Current Connection
          </button>
        )}
      </div>
      {currentConfig && !connectionTested && (
        <p className="text-sm text-zinc-500 mb-4">
          Test the connection first to enable saving.
        </p>
      )}

      {showSaveDialog && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 mb-4">
          <label htmlFor="saved-conn-name" className="block text-sm font-medium text-zinc-300 mb-2">
            Connection name
          </label>
          <input
            id="saved-conn-name"
            type="text"
            value={connectionName}
            onChange={(e) => setConnectionName(e.target.value)}
            placeholder="My Database Connection"
            className={`${inputClass} mb-3`}
            autoFocus
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !connectionName.trim()}
              className="px-3 py-1.5 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowSaveDialog(false)
                setConnectionName('')
                setError(null)
              }}
              className="px-3 py-1.5 text-sm rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="text-sm text-red-400 bg-red-900/30 border border-red-800 rounded-lg px-3 py-2 mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-500 py-4">Loading connections…</div>
      ) : connections.length === 0 ? (
        <div className="text-sm text-zinc-500 italic py-4">
          No saved connections. Save a connection to use it later.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {connections.map((conn) => (
            <div
              key={conn.id}
              role="button"
              tabIndex={0}
              onClick={() => handleLoad(conn.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  handleLoad(conn.id)
                }
              }}
              className="flex justify-between items-center gap-3 p-3 rounded-lg border border-zinc-700 bg-zinc-800/50 cursor-pointer hover:bg-zinc-700/50 transition-colors"
            >
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-zinc-200 truncate">{conn.name}</div>
                <div className="text-xs text-zinc-500 truncate">
                  {conn.host}:{conn.port} / {conn.database}
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => handleDelete(conn.id, e)}
                className="shrink-0 px-2.5 py-1 text-xs font-medium rounded border border-red-800 bg-red-900/60 text-red-200 hover:bg-red-800/60 transition-colors"
                title="Delete connection"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

