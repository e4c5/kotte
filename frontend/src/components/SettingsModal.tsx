import { useState } from 'react'
import { useSettingsStore, type Theme, type DefaultViewMode } from '../stores/settingsStore'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const {
    theme,
    setTheme,
    defaultViewMode,
    setDefaultViewMode,
    queryHistoryLimit,
    setQueryHistoryLimit,
    autoExecuteQuery,
    setAutoExecuteQuery,
    maxNodesForGraph,
    maxEdgesForGraph,
    setMaxNodesForGraph,
    setMaxEdgesForGraph,
    tablePageSize,
    setTablePageSize,
    defaultLayout,
    setDefaultLayout,
    exportImageFormat,
    setExportImageFormat,
    exportImageWidth,
    exportImageHeight,
    setExportImageSize,
    resetSettings,
  } = useSettingsStore()

  const [tempMaxNodes, setTempMaxNodes] = useState(String(maxNodesForGraph))
  const [tempMaxEdges, setTempMaxEdges] = useState(String(maxEdgesForGraph))
  const [tempPageSize, setTempPageSize] = useState(String(tablePageSize))
  const [tempImageWidth, setTempImageWidth] = useState(String(exportImageWidth))
  const [tempImageHeight, setTempImageHeight] = useState(String(exportImageHeight))

  if (!isOpen) return null

  const handleSave = () => {
    const nodes = parseInt(tempMaxNodes, 10)
    const edges = parseInt(tempMaxEdges, 10)
    const pageSize = parseInt(tempPageSize, 10)
    const width = parseInt(tempImageWidth, 10)
    const height = parseInt(tempImageHeight, 10)

    if (!isNaN(nodes) && nodes > 0) setMaxNodesForGraph(nodes)
    if (!isNaN(edges) && edges > 0) setMaxEdgesForGraph(edges)
    if (!isNaN(pageSize) && pageSize > 0) setTablePageSize(pageSize)
    if (!isNaN(width) && width > 0 && !isNaN(height) && height > 0) {
      setExportImageSize(width, height)
    }

    onClose()
  }

  const handleReset = () => {
    if (confirm('Are you sure you want to reset all settings to defaults?')) {
      resetSettings()
      setTempMaxNodes('5000')
      setTempMaxEdges('10000')
      setTempPageSize('50')
      setTempImageWidth('1920')
      setTempImageHeight('1080')
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '2rem',
          maxWidth: '600px',
          maxHeight: '80vh',
          overflow: 'auto',
          width: '90%',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: 0 }}>Settings</h2>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              padding: '0.25rem 0.5rem',
            }}
          >
            ×
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Theme */}
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
              Theme
            </label>
            <select
              value={theme}
              onChange={(e) => setTheme(e.target.value as Theme)}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
              }}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="auto">Auto (System)</option>
            </select>
          </div>

          {/* Default View Mode */}
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
              Default View Mode
            </label>
            <select
              value={defaultViewMode}
              onChange={(e) => setDefaultViewMode(e.target.value as DefaultViewMode)}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
              }}
            >
              <option value="auto">Auto (Based on result)</option>
              <option value="graph">Graph View</option>
              <option value="table">Table View</option>
            </select>
          </div>

          {/* Query Preferences */}
          <div>
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Query Preferences</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                  Query History Limit
                </label>
                <input
                  type="number"
                  min="10"
                  max="500"
                  value={queryHistoryLimit}
                  onChange={(e) => setQueryHistoryLimit(parseInt(e.target.value, 10) || 50)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={autoExecuteQuery}
                    onChange={(e) => setAutoExecuteQuery(e.target.checked)}
                  />
                  Auto-execute queries (experimental)
                </label>
              </div>
            </div>
          </div>

          {/* Visualization Limits */}
          <div>
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Visualization Limits</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                  Max Nodes for Graph
                </label>
                <input
                  type="number"
                  min="100"
                  max="100000"
                  value={tempMaxNodes}
                  onChange={(e) => setTempMaxNodes(e.target.value)}
                  onBlur={() => {
                    const val = parseInt(tempMaxNodes, 10)
                    if (!isNaN(val) && val > 0) setMaxNodesForGraph(val)
                    else setTempMaxNodes(String(maxNodesForGraph))
                  }}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                  Max Edges for Graph
                </label>
                <input
                  type="number"
                  min="100"
                  max="200000"
                  value={tempMaxEdges}
                  onChange={(e) => setTempMaxEdges(e.target.value)}
                  onBlur={() => {
                    const val = parseInt(tempMaxEdges, 10)
                    if (!isNaN(val) && val > 0) setMaxEdgesForGraph(val)
                    else setTempMaxEdges(String(maxEdgesForGraph))
                  }}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                  }}
                />
              </div>
            </div>
          </div>

          {/* Table View Preferences */}
          <div>
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Table View</h3>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                Default Page Size
              </label>
              <input
                type="number"
                min="10"
                max="1000"
                value={tempPageSize}
                onChange={(e) => setTempPageSize(e.target.value)}
                onBlur={() => {
                  const val = parseInt(tempPageSize, 10)
                  if (!isNaN(val) && val > 0) setTablePageSize(val)
                  else setTempPageSize(String(tablePageSize))
                }}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                }}
              />
            </div>
          </div>

          {/* Graph View Preferences */}
          <div>
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Graph View</h3>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                Default Layout
              </label>
              <select
                value={defaultLayout}
                onChange={(e) => setDefaultLayout(e.target.value as any)}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                }}
              >
                <option value="force">Force-Directed</option>
                <option value="hierarchical">Hierarchical</option>
                <option value="radial">Radial</option>
                <option value="grid">Grid</option>
                <option value="random">Random</option>
              </select>
            </div>
          </div>

          {/* Export Preferences */}
          <div>
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Export</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                  Image Format
                </label>
                <select
                  value={exportImageFormat}
                  onChange={(e) => setExportImageFormat(e.target.value as 'png' | 'svg')}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                  }}
                >
                  <option value="png">PNG</option>
                  <option value="svg">SVG</option>
                </select>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                    Export Width (px)
                  </label>
                  <input
                    type="number"
                    min="100"
                    max="10000"
                    value={tempImageWidth}
                    onChange={(e) => setTempImageWidth(e.target.value)}
                    onBlur={() => {
                      const width = parseInt(tempImageWidth, 10)
                      const height = parseInt(tempImageHeight, 10)
                      if (!isNaN(width) && width > 0 && !isNaN(height) && height > 0) {
                        setExportImageSize(width, height)
                      } else {
                        setTempImageWidth(String(exportImageWidth))
                      }
                    }}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.25rem' }}>
                    Export Height (px)
                  </label>
                  <input
                    type="number"
                    min="100"
                    max="10000"
                    value={tempImageHeight}
                    onChange={(e) => setTempImageHeight(e.target.value)}
                    onBlur={() => {
                      const width = parseInt(tempImageWidth, 10)
                      const height = parseInt(tempImageHeight, 10)
                      if (!isNaN(width) && width > 0 && !isNaN(height) && height > 0) {
                        setExportImageSize(width, height)
                      } else {
                        setTempImageHeight(String(exportImageHeight))
                      }
                    }}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem', gap: '1rem' }}>
          <button
            onClick={handleReset}
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #dc3545',
              borderRadius: '4px',
              backgroundColor: 'white',
              color: '#dc3545',
              cursor: 'pointer',
            }}
          >
            Reset to Defaults
          </button>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={onClose}
              style={{
                padding: '0.5rem 1rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: 'white',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              style={{
                padding: '0.5rem 1rem',
                border: 'none',
                borderRadius: '4px',
                backgroundColor: '#007bff',
                color: 'white',
                cursor: 'pointer',
              }}
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

