import { useState } from 'react'
import { useGraphStore } from '../../stores/graphStore'
import { inputClass, selectClass } from './styles'

interface FilterTabProps {
  readonly availableNodeLabels: string[]
  readonly availableEdgeLabels: string[]
}

export default function FilterTab({ availableNodeLabels, availableEdgeLabels }: FilterTabProps) {
  const {
    filters,
    toggleNodeLabel,
    toggleEdgeLabel,
    addPropertyFilter,
    removePropertyFilter,
    clearFilters,
  } = useGraphStore()

  const [newFilter, setNewFilter] = useState({
    label: '',
    property: '',
    value: '',
    operator: 'contains' as 'equals' | 'contains' | 'startsWith' | 'endsWith',
  })

  const handleAddFilter = () => {
    const property = newFilter.property.trim()
    const value = newFilter.value.trim()
    if (!property || !value) return

    const labelTrim = newFilter.label.trim()
    addPropertyFilter({
      ...(labelTrim ? { label: labelTrim } : {}),
      property,
      value,
      operator: newFilter.operator,
    })
    setNewFilter({ label: '', property: '', value: '', operator: 'contains' })
  }

  return (
    <div className="space-y-6">
      <div>
        <h4 className="text-sm font-semibold text-zinc-300 mb-2">Node Labels</h4>
        <div className="flex flex-col gap-2">
          {availableNodeLabels.map((label) => (
            <label key={label} className="flex items-center gap-2 cursor-pointer text-sm text-zinc-200">
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
            <label key={label} className="flex items-center gap-2 cursor-pointer text-sm text-zinc-200">
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
          <div key={idx} className="flex justify-between items-center gap-2 p-2 mb-2 rounded-lg bg-zinc-800 border border-zinc-700">
            <span className="text-xs text-zinc-300 truncate min-w-0">
              {filter.label ? `${filter.label}.` : ''}
              {filter.property} {filter.operator} &quot;{filter.value}&quot;
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
              onChange={(e) => setNewFilter({ ...newFilter, operator: e.target.value as 'equals' | 'contains' | 'startsWith' | 'endsWith' })}
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
  )
}
