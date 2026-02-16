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
}

export default function SavedConnections({
  onLoadConnection,
  currentConfig,
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

  return (
    <div style={{ marginTop: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3>Saved Connections</h3>
        {currentConfig && (
          <button
            type="button"
            onClick={() => setShowSaveDialog(true)}
            style={{
              padding: '0.5rem 1rem',
              fontSize: '0.9rem',
              cursor: 'pointer',
            }}
          >
            Save Current Connection
          </button>
        )}
      </div>

      {showSaveDialog && (
        <div
          style={{
            border: '1px solid #ccc',
            borderRadius: '4px',
            padding: '1rem',
            marginBottom: '1rem',
            backgroundColor: '#f9f9f9',
          }}
        >
          <label>
            Connection Name:
            <input
              type="text"
              value={connectionName}
              onChange={(e) => setConnectionName(e.target.value)}
              placeholder="My Database Connection"
              style={{
                width: '100%',
                padding: '0.5rem',
                marginTop: '0.25rem',
                marginBottom: '0.5rem',
              }}
              autoFocus
            />
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !connectionName.trim()}
              style={{
                padding: '0.5rem 1rem',
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowSaveDialog(false)
                setConnectionName('')
                setError(null)
              }}
              style={{
                padding: '0.5rem 1rem',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <div style={{ color: 'red', marginBottom: '1rem', fontSize: '0.9rem' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div>Loading connections...</div>
      ) : connections.length === 0 ? (
        <div style={{ color: '#666', fontStyle: 'italic' }}>
          No saved connections. Save a connection to use it later.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {connections.map((conn) => (
            <div
              key={conn.id}
              style={{
                border: '1px solid #ddd',
                borderRadius: '4px',
                padding: '0.75rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                backgroundColor: '#fff',
              }}
              onClick={() => handleLoad(conn.id)}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f5f5f5'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#fff'
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                  {conn.name}
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  {conn.host}:{conn.port} / {conn.database}
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => handleDelete(conn.id, e)}
                style={{
                  padding: '0.25rem 0.5rem',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  backgroundColor: '#dc3545',
                  color: 'white',
                  border: 'none',
                  borderRadius: '3px',
                }}
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

