import { useState } from 'react'
import LayoutTab from './GraphControls/LayoutTab'
import FilterTab from './GraphControls/FilterTab'
import StyleTab from './GraphControls/StyleTab'

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
  const [activeTab, setActiveTab] = useState<'layout' | 'filter' | 'style'>('layout')

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
        {activeTab === 'layout' && <LayoutTab />}
        {activeTab === 'filter' && (
          <FilterTab
            availableNodeLabels={availableNodeLabels}
            availableEdgeLabels={availableEdgeLabels}
          />
        )}
        {activeTab === 'style' && (
          <StyleTab
            availableNodeLabels={availableNodeLabels}
            availableEdgeLabels={availableEdgeLabels}
          />
        )}
      </div>
    </div>
  )
}
