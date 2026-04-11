import { useGraphStore } from '../../stores/graphStore'
import { inputClass, selectClass } from './styles'

interface StyleTabProps {
  readonly availableNodeLabels: string[]
  readonly availableEdgeLabels: string[]
}

export default function StyleTab({ availableNodeLabels, availableEdgeLabels }: StyleTabProps) {
  const {
    nodeStyles,
    edgeStyles,
    setNodeStyle,
    setEdgeStyle,
    edgeWidthMapping,
    setEdgeWidthMapping,
    resetStyles,
  } = useGraphStore()

  return (
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
          const idPrefix = `node-style-${label.replace(/\s+/g, '-')}`
          return (
            <div key={label} className="p-3 mb-2 rounded-lg border border-zinc-700 bg-zinc-800/50">
              <div className="font-semibold text-zinc-200 mb-2 text-sm">{label}</div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-color`} className="text-xs text-zinc-400 w-14 shrink-0">Color:</label>
                  <input
                    id={`${idPrefix}-color`}
                    type="color"
                    value={style.color}
                    onChange={(e) => setNodeStyle(label, { ...style, color: e.target.value })}
                    className="w-12 h-7 rounded cursor-pointer bg-zinc-800 border border-zinc-600"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-size`} className="text-xs text-zinc-400 w-14 shrink-0">Size:</label>
                  <input
                    id={`${idPrefix}-size`}
                    type="range"
                    min="5"
                    max="30"
                    value={style.size}
                    onChange={(e) => setNodeStyle(label, { ...style, size: parseInt(e.target.value) })}
                    className="flex-1 accent-blue-500"
                  />
                  <span className="text-xs text-zinc-400 w-7">{style.size}</span>
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-caption`} className="text-xs text-zinc-400 w-14 shrink-0">Caption:</label>
                  <input
                    id={`${idPrefix}-caption`}
                    type="text"
                    value={style.captionField || 'label'}
                    onChange={(e) => setNodeStyle(label, { ...style, captionField: e.target.value })}
                    placeholder="Property name or 'label'"
                    className={`${inputClass} flex-1 py-1.5 text-xs`}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-show`} className="text-xs text-zinc-400 w-14 shrink-0">Show:</label>
                  <input
                    id={`${idPrefix}-show`}
                    type="checkbox"
                    checked={style.showLabel !== false}
                    onChange={(e) => setNodeStyle(label, { ...style, showLabel: e.target.checked })}
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
          const idPrefix = `edge-style-${label.replace(/\s+/g, '-')}`
          return (
            <div key={label} className="p-3 mb-2 rounded-lg border border-zinc-700 bg-zinc-800/50">
              <div className="font-semibold text-zinc-200 mb-2 text-sm">{label}</div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-color`} className="text-xs text-zinc-400 w-14 shrink-0">Color:</label>
                  <input
                    id={`${idPrefix}-color`}
                    type="color"
                    value={style.color}
                    onChange={(e) => setEdgeStyle(label, { ...style, color: e.target.value })}
                    className="w-12 h-7 rounded cursor-pointer bg-zinc-800 border border-zinc-600"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-width`} className="text-xs text-zinc-400 w-14 shrink-0">Width:</label>
                  <input
                    id={`${idPrefix}-width`}
                    type="range"
                    min="1"
                    max="10"
                    value={style.size}
                    onChange={(e) => setEdgeStyle(label, { ...style, size: parseInt(e.target.value) })}
                    className="flex-1 accent-blue-500"
                  />
                  <span className="text-xs text-zinc-400 w-7">{style.size}</span>
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-caption`} className="text-xs text-zinc-400 w-14 shrink-0">Caption:</label>
                  <input
                    id={`${idPrefix}-caption`}
                    type="text"
                    value={style.captionField || 'label'}
                    onChange={(e) => setEdgeStyle(label, { ...style, captionField: e.target.value })}
                    placeholder="Property name or 'label'"
                    className={`${inputClass} flex-1 py-1.5 text-xs`}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor={`${idPrefix}-show`} className="text-xs text-zinc-400 w-14 shrink-0">Show:</label>
                  <input
                    id={`${idPrefix}-show`}
                    type="checkbox"
                    checked={style.showLabel !== false}
                    onChange={(e) => setEdgeStyle(label, { ...style, showLabel: e.target.checked })}
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
              onChange={(e) => setEdgeWidthMapping({ enabled: e.target.checked })}
              className="rounded border-zinc-600 bg-zinc-800 text-blue-500"
            />
            <span>Enable width mapping</span>
          </label>
          {edgeWidthMapping.enabled && (
            <>
              <div>
                <label htmlFor="edge-width-property" className="block text-xs text-zinc-400 mb-1">Property:</label>
                <input
                  id="edge-width-property"
                  type="text"
                  value={edgeWidthMapping.property || ''}
                  onChange={(e) => setEdgeWidthMapping({ property: e.target.value || null })}
                  placeholder="Enter property name (e.g., weight, count)"
                  className={inputClass}
                />
                <p className="text-xs text-zinc-500 mt-1">Enter a numeric property name to map to edge width</p>
              </div>
              <div>
                <label htmlFor="edge-width-scale" className="block text-xs text-zinc-400 mb-1">Scale Type:</label>
                <select
                  id="edge-width-scale"
                  value={edgeWidthMapping.scaleType}
                  onChange={(e) => setEdgeWidthMapping({ scaleType: e.target.value as 'linear' | 'log' })}
                  className={selectClass}
                >
                  <option value="linear">Linear</option>
                  <option value="log">Logarithmic</option>
                </select>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label htmlFor="edge-width-min" className="block text-xs text-zinc-400 mb-1">Min Width:</label>
                  <input
                    id="edge-width-min"
                    type="number"
                    min="0.5"
                    max="20"
                    step="0.5"
                    value={edgeWidthMapping.minWidth}
                    onChange={(e) => setEdgeWidthMapping({ minWidth: Number.parseFloat(e.target.value) || 1 })}
                    className={inputClass}
                  />
                </div>
                <div className="flex-1">
                  <label htmlFor="edge-width-max" className="block text-xs text-zinc-400 mb-1">Max Width:</label>
                  <input
                    id="edge-width-max"
                    type="number"
                    min="0.5"
                    max="20"
                    step="0.5"
                    value={edgeWidthMapping.maxWidth}
                    onChange={(e) => setEdgeWidthMapping({ maxWidth: Number.parseFloat(e.target.value) || 10 })}
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
  )
}
