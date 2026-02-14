import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'

export default function WorkspacePage() {
  const navigate = useNavigate()
  const { status, refreshStatus, disconnect } = useSessionStore()

  useEffect(() => {
    refreshStatus()
  }, [refreshStatus])

  useEffect(() => {
    if (status && !status.connected) {
      navigate('/')
    }
  }, [status, navigate])

  const handleDisconnect = async () => {
    await disconnect()
    navigate('/')
  }

  if (!status || !status.connected) {
    return <div>Loading...</div>
  }

  return (
    <div style={{ padding: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <h2>Workspace</h2>
        <button onClick={handleDisconnect}>Disconnect</button>
      </div>
      <div>
        <p>Connected to: {status.database} on {status.host}:{status.port}</p>
        {status.current_graph && <p>Current graph: {status.current_graph}</p>}
      </div>
      <div style={{ marginTop: '2rem' }}>
        <p>Workspace UI coming soon...</p>
      </div>
    </div>
  )
}

