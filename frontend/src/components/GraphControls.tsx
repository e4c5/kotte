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

  const inputClass =
    'w-full px-3 py-2 text-sm bg-zinc-800 border border-zinc-600 rounded-lg text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500'
  const selectClass =
    'w-full px-3 py-2 text-sm bg-zinc-800 border border-zinc-600 rounded-lg text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none cursor-pointer'

  return (
    <div className="absolute top-2 right-2 w-[350px] max-h-[80vh] overflow-auto rounded-lg border border-zinc-700 bg-zinc-900 shadow-xl z-[1000]">
      {/* Header */}
      <div className="flex justify-between items-center px-4 py-3 border-b border-zinc-700">
        <h3 className="m-0 text-sm font-semibold text-zinc-100 uppercase tracking-wide">
          Graph Controls
        </h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700 text-xl leading-none"
            aria-label="Close graph controls"
          >
            ×
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-700">
        {(['layout', 'filter', 'style'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2.5 text-sm font-medium capitalize border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-blue-500 bg-zinc-800 text-zinc-100'
                : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-4 text-zinc-100">
        {/* Layout Tab */}
        {activeTab === 'layout' && (
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Layout Algorithm
            </label>
            <select
              value={layout}
              onChange={(e) => setLayout(e.target.value as LayoutType)}
              className={selectClass}
            >
              <option value="force">Force-Directed</option>
              <option value="hierarchical">Hierarchical</option>
              <option value="radial">Radial</option>
              <option value="grid">Grid</option>
              <option value="random">Random</option>
              <option value="cluster">Cluster (hierarchical)</option>
              <option value="partition">Partition (sunburst-style)</option>
              <option value="pack">Pack (circle packing)</option>
            </select>
            <p className="text-xs text-zinc-500 mt-2">
              {layout === 'force' && 'Dynamic force-directed layout with physics simulation'}
              {layout === 'hierarchical' && 'Organized by labels in rows'}
              {layout === 'radial' && 'Circular arrangement around center'}
              {layout === 'grid' && 'Regular grid pattern'}
              {layout === 'random' && 'Random initial positions'}
              {layout === 'cluster' && 'Hierarchical cluster layout grouped by node label'}
              {layout === 'partition' && 'Space-filling partition layout grouped by node label'}
              {layout === 'pack' && 'Circle packing layout grouped by node label'}
            </p>
          </div>
        )}

        {/* Filter Tab */}
        {activeTab === 'filter' && (
          <div className="space-y-6">
            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Node Labels</h4>
              <div className="flex flex-col gap-2">
                {availableNodeLabels.map((label) => (
                  <label
                    key={label}
                    className="flex items-center gap-2 cursor-pointer text-sm text-zinc-200"
                  >
                    <input
                      type="checkbox"
                      checked={filters.nodeLabels.has(label)}
                      onChange={() => toggleNodeLabel(label)}
                      className="rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Edge Labels</h4>
              <div className="flex flex-col gap-2">
                {availableEdgeLabels.map((label) => (
                  <label
                    key={label}
                    className="flex items-center gap-2 cursor-pointer text-sm text-zinc-200"
                  >
                    <input
                      type="checkbox"
                      checked={filters.edgeLabels.has(label)}
                      onChange={() => toggleEdgeLabel(label)}
                      className="rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Property Filters</h4>
              {filters.propertyFilters.map((filter, idx) => (
                <div
                  key={idx}
                  className="flex justify-between items-center gap-2 p-2 mb-2 rounded-lg bg-zinc-800 border border-zinc-700"
                >
                  <span className="text-xs text-zinc-300 truncate min-w-0">
                    {filter.label}.{filter.property} {filter.operator} &quot;{filter.value}&quot;
                  </span>
                  <button
                    type="button"
                    onClick={() => removePropertyFilter(idx)}
                    className="shrink-0 px-2 py-1 text-xs rounded border border-zinc-600 text-zinc-300 hover:bg-zinc-700"
                  >
                    Remove
                  </button>
                </div>
              ))}

              <div className="flex flex-col gap-2">
                <input
                  type="text"
                  placeholder="Label (optional)"
                  value={newFilter.label}
                  onChange={(e) => setNewFilter({ ...newFilter, label: e.target.value })}
                  className={inputClass}
                />
                <input
                  type="text"
                  placeholder="Property name"
                  value={newFilter.property}
                  onChange={(e) => setNewFilter({ ...newFilter, property: e.target.value })}
                  className={inputClass}
                />
                <div className="flex gap-2">
                  <select
                    value={newFilter.operator}
                    onChange={(e) =>
                      setNewFilter({
                        ...newFilter,
                        operator: e.target.value as typeof newFilter.operator,
                      })
                    }
                    className={`${selectClass} flex-1`}
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
                    className={`${inputClass} flex-[2]`}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleAddFilter}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500"
                >
                  Add Filter
                </button>
              </div>
            </div>

            <button
              type="button"
              onClick={clearFilters}
              className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800"
            >
              Clear All Filters
            </button>
          </div>
        )}

        {/* Style Tab */}
        {activeTab === 'style' && (
          <div className="space-y-6">
            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Node Styles</h4>
              {availableNodeLabels.map((label) => {
                const style = nodeStyles[label] || {
                  color: '#1f77b4',
                  size: 10,
                  captionField: 'label',
                  showLabel: true,
                }
                return (
                  <div
                    key={label}
                    className="p-3 mb-2 rounded-lg border border-zinc-700 bg-zinc-800/50"
                  >
                    <div className="font-semibold text-zinc-200 mb-2 text-sm">{label}</div>
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Color:</label>
                        <input
                          type="color"
                          value={style.color}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, color: e.target.value })
                          }
                          className="w-12 h-7 rounded cursor-pointer bg-zinc-800 border border-zinc-600"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Size:</label>
                        <input
                          type="range"
                          min="5"
                          max="30"
                          value={style.size}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, size: parseInt(e.target.value) })
                          }
                          className="flex-1 accent-blue-500"
                        />
                        <span className="text-xs text-zinc-400 w-7">{style.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Caption:</label>
                        <input
                          type="text"
                          value={style.captionField || 'label'}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, captionField: e.target.value })
                          }
                          placeholder="Property name or 'label'"
                          className={`${inputClass} flex-1 py-1.5 text-xs`}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Show:</label>
                        <input
                          type="checkbox"
                          checked={style.showLabel !== false}
                          onChange={(e) =>
                            setNodeStyle(label, { ...style, showLabel: e.target.checked })
                          }
                          className="rounded border-zinc-600 bg-zinc-800 text-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Edge Styles</h4>
              {availableEdgeLabels.map((label) => {
                const style = edgeStyles[label] || {
                  color: '#999',
                  size: 2,
                  captionField: 'label',
                  showLabel: true,
                }
                return (
                  <div
                    key={label}
                    className="p-3 mb-2 rounded-lg border border-zinc-700 bg-zinc-800/50"
                  >
                    <div className="font-semibold text-zinc-200 mb-2 text-sm">{label}</div>
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Color:</label>
                        <input
                          type="color"
                          value={style.color}
                          onChange={(e) =>
                            setEdgeStyle(label, { ...style, color: e.target.value })
                          }
                          className="w-12 h-7 rounded cursor-pointer bg-zinc-800 border border-zinc-600"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Width:</label>
                        <input
                          type="range"
                          min="1"
                          max="10"
                          value={style.size}
                          onChange={(e) =>
                            setEdgeStyle(label, { ...style, size: parseInt(e.target.value) })
                          }
                          className="flex-1 accent-blue-500"
                        />
                        <span className="text-xs text-zinc-400 w-7">{style.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Caption:</label>
                        <input
                          type="text"
                          value={style.captionField || 'label'}
                          onChange={(e) =>
                            setEdgeStyle(label, { ...style, captionField: e.target.value })
                          }
                          placeholder="Property name or 'label'"
                          className={`${inputClass} flex-1 py-1.5 text-xs`}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 w-14 shrink-0">Show:</label>
                        <input
                          type="checkbox"
                          checked={style.showLabel !== false}
                          onChange={(e) =>
                            setEdgeStyle(label, { ...style, showLabel: e.target.checked })
                          }
                          className="rounded border-zinc-600 bg-zinc-800 text-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Edge Width Mapping</h4>
              <div className="flex flex-col gap-3">
                <label className="flex items-center gap-2 cursor-pointer text-sm text-zinc-200">
                  <input
                    type="checkbox"
                    checked={edgeWidthMapping.enabled}
                    onChange={(e) =>
                      setEdgeWidthMapping({ enabled: e.target.checked })
                    }
                    className="rounded border-zinc-600 bg-zinc-800 text-blue-500"
                  />
                  <span>Enable width mapping</span>
                </label>
                {edgeWidthMapping.enabled && (
                  <>
                    <div>
                      <label className="block text-xs text-zinc-400 mb-1">Property:</label>
                      <input
                        type="text"
                        value={edgeWidthMapping.property || ''}
                        onChange={(e) =>
                          setEdgeWidthMapping({ property: e.target.value || null })
                        }
                        placeholder="Enter property name (e.g., weight, count)"
                        className={inputClass}
                      />
                      <p className="text-xs text-zinc-500 mt-1">
                        Enter a numeric property name to map to edge width
                      </p>
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-400 mb-1">Scale Type:</label>
                      <select
                        value={edgeWidthMapping.scaleType}
                        onChange={(e) =>
                          setEdgeWidthMapping({
                            scaleType: e.target.value as 'linear' | 'log',
                          })
                        }
                        className={selectClass}
                      >
                        <option value="linear">Linear</option>
                        <option value="log">Logarithmic</option>
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <label className="block text-xs text-zinc-400 mb-1">Min Width:</label>
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
                          className={inputClass}
                        />
                      </div>
                      <div className="flex-1">
                        <label className="block text-xs text-zinc-400 mb-1">Max Width:</label>
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
                          className={inputClass}
                        />
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={resetStyles}
              className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800"
            >
              Reset All Styles
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
