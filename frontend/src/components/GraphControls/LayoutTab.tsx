import { useGraphStore, type LayoutType } from '../../stores/graphStore'
import { selectClass } from './styles'

export default function LayoutTab() {
  const { layout, setLayout } = useGraphStore()

  return (
    <div>
      <label className="block text-sm font-medium text-zinc-300 mb-2" htmlFor="layout-select">
        Layout Algorithm
      </label>
      <select
        id="layout-select"
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
  )
}
