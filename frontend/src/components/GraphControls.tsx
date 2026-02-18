import { useState } from 'react'
import {
  useGraphStore,
  type LayoutType,
} from '../stores/graphStore'

interface GraphControlsProps {
  availableNodeLabels: string[]
  availableEdgeLabels: string[]
  onClose?: () => void
}

export default function GraphControls({
  availableNodeLabels,
  availableEdgeLabels,
  onClose,
}: GraphControlsProps) {
  const {
    layout,
    setLayout,
    nodeStyles,
    edgeStyles,
    setNodeStyle,
    setEdgeStyle,
    edgeWidthMapping,
    setEdgeWidthMapping,
    filters,
    toggleNodeLabel,
    toggleEdgeLabel,
    addPropertyFilter,
    removePropertyFilter,
    clearFilters,
    resetStyles,
  } = useGraphStore()

  const [activeTab, setActiveTab] = useState<'layout' | 'filter' | 'style'>('layout')
  // const [editingLabel, setEditingLabel] = useState<{
  //   type: 'node' | 'edge'
  //   label: string
  // } | null>(null) // Reserved for future use

  const [newFilter, setNewFilter] = useState({
    label: '',
    property: '',
    value: '',
    operator: 'contains' as 'equals' | 'contains' | 'startsWith' | 'endsWith',
  })

  const handleAddFilter = () => {
    if (newFilter.label && newFilter.property && newFilter.value) {
      addPropertyFilter({
        label: newFilter.label,
        property: newFilter.property,
        value: newFilter.value,
        operator: newFilter.operator,
      })
      setNewFilter({ label: '', property: '', value: '', operator: 'contains' })
    }
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        width: '350px',
        backgroundColor: 'white',
        border: '1px solid #ccc',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        zIndex: 1000,
        maxHeight: '80vh',
        overflow: 'auto',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '1rem',
          borderBottom: '1px solid #eee',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Graph Controls</h3>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              color: '#999',
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #eee' }}>
        {(['layout', 'filter', 'style'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              flex: 1,
              padding: '0.75rem',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid #007bff' : '2px solid transparent',
              backgroundColor: activeTab === tab ? '#f0f8ff' : 'white',
              cursor: 'pointer',
              textTransform: 'capitalize',
              fontWeight: activeTab === tab ? 'bold' : 'normal',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: '1rem' }}>
        {/* Layout Tab */}
        {activeTab === 'layout' && (
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
              Layout Algorithm
            </label>
            <select
              value={layout}
              onChange={(e) => setLayout(e.target.value as LayoutType)}
              style={{
                width: '100%',
                padding: '0.5rem',
                fontSize: '0.9rem',
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
            <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem' }}>
              {layout === 'force' && 'Dynamic force-directed layout with physics simulation'}
              {layout === 'hierarchical' && 'Organized by labels in rows'}
              {layout === 'radial' && 'Circular arrangement around center'}
              {layout === 'grid' && 'Regular grid pattern'}
              {layout === 'random' && 'Random initial positions'}
            </p>
          </div>
        )}

        {/* Filter Tab */}
        {activeTab === 'filter' && (
          <div>
            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Node Labels</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {availableNodeLabels.map((label) => (
                  <label
                    key={label}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={filters.nodeLabels.has(label)}
                      onChange={() => toggleNodeLabel(label)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Edge Labels</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {availableEdgeLabels.map((label) => (
                  <label
                    key={label}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={filters.edgeLabels.has(label)}
                      onChange={() => toggleEdgeLabel(label)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Property Filters</h4>
              {filters.propertyFilters.map((filter, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '0.5rem',
                    marginBottom: '0.5rem',
                    backgroundColor: '#f9f9f9',
                    borderRadius: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ fontSize: '0.85rem' }}>
                    {filter.label}.{filter.property} {filter.operator} "{filter.value}"
                  </span>
                  <button
                    onClick={() => removePropertyFilter(idx)}
                    style={{
                      padding: '0.25rem 0.5rem',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                      backgroundColor: 'white',
                    }}
                  >
                    Remove
                  </button>
                </div>
              ))}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <input
                  type="text"
                  placeholder="Label (optional)"
                  value={newFilter.label}
                  onChange={(e) => setNewFilter({ ...newFilter, label: e.target.value })}
                  style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
                />
                <input
                  type="text"
                  placeholder="Property name"
                  value={newFilter.property}
                  onChange={(e) => setNewFilter({ ...newFilter, property: e.target.value })}
                  style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
                />
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <select
                    value={newFilter.operator}
                    onChange={(e) =>
                      setNewFilter({
                        ...newFilter,
                        operator: e.target.value as typeof newFilter.operator,
                      })
                    }
                    style={{
                      flex: 1,
                      padding: '0.5rem',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                    }}
                  >
                    <option value="equals">equals</option>
                    <option value="contains">contains</option>
                    <option value="startsWith">starts with</option>
                    <option value="endsWith">ends with</option>
                  </select>
                  <input
                    type="text"
                    placeholder="Value"
                    value={newFilter.value}
                    onChange={(e) => setNewFilter({ ...newFilter, value: e.target.value })}
                    style={{
                      flex: 2,
                      padding: '0.5rem',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <button
                  onClick={handleAddFilter}
                  style={{
                    padding: '0.5rem',
                    cursor: 'pointer',
                    border: '1px solid #007bff',
                    borderRadius: '4px',
                    backgroundColor: '#007bff',
                    color: 'white',
                  }}
                >
                  Add Filter
                </button>
              </div>
            </div>

            <button
              onClick={clearFilters}
              style={{
                width: '100%',
                padding: '0.5rem',
                cursor: 'pointer',
                border: '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: 'white',
              }}
            >
              Clear All Filters
            </button>
          </div>
        )}

        {/* Style Tab */}
        {activeTab === 'style' && (
          <div>
            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Node Styles</h4>
              {availableNodeLabels.map((label) => {
                const style = nodeStyles[label] || {
                  color: '#1f77b4',
                  size: 10,
                  captionField: 'label',
                }
                return (
                  <div
                    key={label}
                    style={{
                      padding: '0.75rem',
                      marginBottom: '0.5rem',
                      border: '1px solid #eee',
                      borderRadius: '4px',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>{label}</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.85rem', width: '60px' }}>Color:</label>
                        <input
                          type="color"
                          value={style.color}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, color: e.target.value })
                          }
                          style={{ width: '60px', height: '30px', cursor: 'pointer' }}
                        />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.85rem', width: '60px' }}>Size:</label>
                        <input
                          type="range"
                          min="5"
                          max="30"
                          value={style.size}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, size: parseInt(e.target.value) })
                          }
                          style={{ flex: 1 }}
                        />
                        <span style={{ fontSize: '0.85rem', width: '30px' }}>{style.size}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.85rem', width: '60px' }}>Caption:</label>
                        <input
                          type="text"
                          value={style.captionField || 'label'}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, captionField: e.target.value })
                          }
                          placeholder="Property name or 'label'"
                          style={{
                            flex: 1,
                            padding: '0.25rem',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                            fontSize: '0.85rem',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Edge Styles</h4>
              {availableEdgeLabels.map((label) => {
                const style = edgeStyles[label] || { color: '#999', size: 2 }
                return (
                  <div
                    key={label}
                    style={{
                      padding: '0.75rem',
                      marginBottom: '0.5rem',
                      border: '1px solid #eee',
                      borderRadius: '4px',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>{label}</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.85rem', width: '60px' }}>Color:</label>
                        <input
                          type="color"
                          value={style.color}
                          onChange={(e) =>
                            setEdgeStyle(label, { ...style, color: e.target.value })
                          }
                          style={{ width: '60px', height: '30px', cursor: 'pointer' }}
                        />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.85rem', width: '60px' }}>Width:</label>
                        <input
                          type="range"
                          min="1"
                          max="10"
                          value={style.size}
                          onChange={(e) =>
                            setEdgeStyle(label, { ...style, size: parseInt(e.target.value) })
                          }
                          style={{ flex: 1 }}
                        />
                        <span style={{ fontSize: '0.85rem', width: '30px' }}>{style.size}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Edge Width Mapping</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={edgeWidthMapping.enabled}
                    onChange={(e) =>
                      setEdgeWidthMapping({ enabled: e.target.checked })
                    }
                  />
                  <span>Enable width mapping</span>
                </label>
                {edgeWidthMapping.enabled && (
                  <>
                    <div>
                      <label style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                        Property:
                      </label>
                      <input
                        type="text"
                        value={edgeWidthMapping.property || ''}
                        onChange={(e) =>
                          setEdgeWidthMapping({ property: e.target.value || null })
                        }
                        placeholder="Enter property name (e.g., weight, count)"
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          border: '1px solid #ccc',
                          borderRadius: '4px',
                        }}
                      />
                      <p style={{ fontSize: '0.75rem', color: '#666', marginTop: '0.25rem' }}>
                        Enter a numeric property name to map to edge width
                      </p>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                        Scale Type:
                      </label>
                      <select
                        value={edgeWidthMapping.scaleType}
                        onChange={(e) =>
                          setEdgeWidthMapping({
                            scaleType: e.target.value as 'linear' | 'log',
                          })
                        }
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          border: '1px solid #ccc',
                          borderRadius: '4px',
                        }}
                      >
                        <option value="linear">Linear</option>
                        <option value="log">Logarithmic</option>
                      </select>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                          Min Width:
                        </label>
                        <input
                          type="number"
                          min="0.5"
                          max="20"
                          step="0.5"
                          value={edgeWidthMapping.minWidth}
                          onChange={(e) =>
                            setEdgeWidthMapping({
                              minWidth: parseFloat(e.target.value) || 1,
                            })
                          }
                          style={{
                            width: '100%',
                            padding: '0.5rem',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                          Max Width:
                        </label>
                        <input
                          type="number"
                          min="0.5"
                          max="20"
                          step="0.5"
                          value={edgeWidthMapping.maxWidth}
                          onChange={(e) =>
                            setEdgeWidthMapping({
                              maxWidth: parseFloat(e.target.value) || 10,
                            })
                          }
                          style={{
                            width: '100%',
                            padding: '0.5rem',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                          }}
                        />
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            <button
              onClick={resetStyles}
              style={{
                width: '100%',
                padding: '0.5rem',
                cursor: 'pointer',
                border: '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: 'white',
              }}
            >
              Reset All Styles
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

