import { useEffect, useState } from 'react'
import { graphAPI, type GraphInfo, type GraphMetadata } from '../services/graph'

interface MetadataSidebarProps {
  currentGraph?: string
  onGraphSelect: (graphName: string) => void
  onQueryTemplate: (query: string) => void
}

export default function MetadataSidebar({
  currentGraph,
  onGraphSelect,
  onQueryTemplate,
}: MetadataSidebarProps) {
  const [graphs, setGraphs] = useState<GraphInfo[]>([])
  const [metadata, setMetadata] = useState<GraphMetadata | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadGraphs()
  }, [])

  useEffect(() => {
    if (currentGraph) {
      loadMetadata(currentGraph)
    } else {
      setMetadata(null)
    }
  }, [currentGraph])

  const loadGraphs = async () => {
    try {
      const graphList = await graphAPI.listGraphs()
      setGraphs(graphList)
      if (graphList.length > 0 && !currentGraph) {
        onGraphSelect(graphList[0].name)
      }
    } catch (error) {
      console.error('Failed to load graphs:', error)
    }
  }

  const loadMetadata = async (graphName: string) => {
    setLoading(true)
    try {
      const meta = await graphAPI.getMetadata(graphName)
      setMetadata(meta)
    } catch (error) {
      console.error('Failed to load metadata:', error)
    } finally {
      setLoading(false)
    }
  }

  const generateQuery = (type: 'node' | 'edge', label: string) => {
    if (type === 'node') {
      return `MATCH (n:${label}) RETURN n LIMIT 100`
    } else {
      return `MATCH ()-[r:${label}]->() RETURN r LIMIT 100`
    }
  }

  return (
    <div
      style={{
        width: '300px',
        borderRight: '1px solid #ccc',
        height: '100%',
        overflow: 'auto',
        backgroundColor: '#f9f9f9',
      }}
    >
      <div style={{ padding: '1rem', borderBottom: '1px solid #ccc' }}>
        <h3 style={{ margin: 0, marginBottom: '1rem' }}>Graphs</h3>
        <select
          value={currentGraph || ''}
          onChange={(e) => onGraphSelect(e.target.value)}
          style={{
            width: '100%',
            padding: '0.5rem',
            fontSize: '0.9rem',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        >
          <option value="">Select a graph...</option>
          {graphs.map((g) => (
            <option key={g.name} value={g.name}>
              {g.name}
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>
      )}

      {metadata && !loading && (
        <div style={{ padding: '1rem' }}>
          <h4 style={{ marginTop: 0 }}>Node Labels</h4>
          <div style={{ marginBottom: '1.5rem' }}>
            {metadata.node_labels.map((label) => (
              <div
                key={label.label}
                style={{
                  padding: '0.5rem',
                  marginBottom: '0.5rem',
                  backgroundColor: 'white',
                  borderRadius: '4px',
                  border: '1px solid #ddd',
                  cursor: 'pointer',
                }}
                onClick={() => onQueryTemplate(generateQuery('node', label.label))}
                title="Click to generate query"
              >
                <div style={{ fontWeight: 'bold' }}>{label.label}</div>
                <div style={{ fontSize: '0.85rem', color: '#666' }}>
                  {label.count.toLocaleString()} nodes
                </div>
                {label.properties.length > 0 && (
                  <div style={{ fontSize: '0.75rem', color: '#999', marginTop: '0.25rem' }}>
                    Properties: {label.properties.slice(0, 3).join(', ')}
                    {label.properties.length > 3 && '...'}
                  </div>
                )}
              </div>
            ))}
          </div>

          <h4>Edge Labels</h4>
          <div>
            {metadata.edge_labels.map((label) => (
              <div
                key={label.label}
                style={{
                  padding: '0.5rem',
                  marginBottom: '0.5rem',
                  backgroundColor: 'white',
                  borderRadius: '4px',
                  border: '1px solid #ddd',
                  cursor: 'pointer',
                }}
                onClick={() => onQueryTemplate(generateQuery('edge', label.label))}
                title="Click to generate query"
              >
                <div style={{ fontWeight: 'bold' }}>{label.label}</div>
                <div style={{ fontSize: '0.85rem', color: '#666' }}>
                  {label.count.toLocaleString()} edges
                </div>
                {label.properties.length > 0 && (
                  <div style={{ fontSize: '0.75rem', color: '#999', marginTop: '0.25rem' }}>
                    Properties: {label.properties.slice(0, 3).join(', ')}
                    {label.properties.length > 3 && '...'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

