import type { GraphNode, GraphEdge } from '../components/GraphView'
import type { LabelStyle } from '../stores/graphStore'
import { getNodeLabelColor } from './nodeColors'

// Node label colors are routed through `getNodeLabelColor` so the graph
// canvas, the metadata sidebar pills, and any other surface that displays
// a label-coloured swatch agree on the colour for a given label
// (ROADMAP A6 — fixes the case where d3.scaleOrdinal and nodeColors had
// independent insertion-order counters and the same label could land on
// two different palette indices).

/** Parse a numeric edge-width property; objects/symbols do not stringify to useful numbers. */
function coerceNumericFromProperty(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'bigint') {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  if (typeof value === 'string') {
    const n = Number.parseFloat(value.trim())
    return Number.isNaN(n) ? null : n
  }
  return null
}

/** String form for non-object, non-null values (null/undefined handled by callers). */
function stringFromNonObject(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  if (typeof value === 'boolean') return String(value)
  if (typeof value === 'bigint') return String(value)
  if (typeof value === 'symbol') return String(value)
  if (typeof value === 'function') return String(value)
  return ''
}

/**
 * Default colour for a node label, when the user hasn't overridden it via
 * `nodeStyles`. Delegates to the shared `getNodeLabelColor` so this returns
 * the same hex as the metadata-sidebar pill for the same label.
 */
export function getDefaultNodeColor(label: string): string {
  return getNodeLabelColor(label)
}

export const getNodeStyle = (node: GraphNode, nodeStyles: Record<string, LabelStyle>): LabelStyle => {
  return nodeStyles[node.label] || {
    color: getDefaultNodeColor(node.label),
    size: 10,
    captionField: 'label',
  }
}

export const getEdgeStyle = (
  edge: GraphEdge,
  edgeStyles: Record<string, LabelStyle>,
  // d3.ScaleLinear / d3.ScaleLogarithmic union; specifying it precisely would
  // pull every consumer into the d3 generic vortex for negligible benefit.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  edgeWidthScale: any,
  edgeWidthProperty?: string | null
): LabelStyle => {
  const baseStyle = edgeStyles[edge.label] || {
    color: '#999',
    size: 2,
    captionField: 'label',
    showLabel: true,
  }
  
  // Apply width mapping if enabled
  if (edgeWidthScale && edgeWidthProperty) {
    const propValue = edge.properties[edgeWidthProperty]
    if (propValue !== undefined && propValue !== null) {
      const numValue = coerceNumericFromProperty(propValue)
      if (numValue !== null) {
        return {
          ...baseStyle,
          size: edgeWidthScale(numValue),
        }
      }
    }
  }
  
  return baseStyle
}

const shortenLongIdentifier = (s: string): string => {
  if (s.length > 40 && (s.includes('.') || s.includes('#'))) {
    const parts = s.includes('#') ? s.split('#') : s.split('.')
    return parts.pop() || s
  }
  return s
}

const safeStringify = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (e) {
      console.warn('JSON.stringify failed for graph style value', e)
      return '[unserializable]'
    }
  }
  return stringFromNonObject(value)
}

const getDescriptivePropertyValue = (properties: Record<string, unknown>): string | null => {
  const nameKeys = ['name', 'title', 'fqn', 'signature']
  for (const key of nameKeys) {
    const value = properties[key]
    if (value === null || value === undefined) continue
    if (typeof value === 'object') {
      const s = safeStringify(value).trim()
      if (s !== '' && s !== '{}') {
        return s
      }
      continue
    }
    const s = stringFromNonObject(value).trim()
    if (s !== '') {
      return s
    }
  }
  return null
}

export const getNodeCaption = (
  node: GraphNode,
  nodeStyles: Record<string, LabelStyle>
): string => {
  const style = getNodeStyle(node, nodeStyles)
  if (style.showLabel === false) return ''

  const field = style.captionField || 'label'
  let caption = field === 'label' ? node.label : safeStringify(node.properties[field] ?? node.id)

  // If caption is just the label, try to find a better property
  if (caption === node.label && node.properties) {
    const descriptive = getDescriptivePropertyValue(node.properties)
    if (descriptive) {
      caption = shortenLongIdentifier(descriptive)
    }
  }
  
  return caption
}

export const getEdgeCaption = (
  edge: GraphEdge,
  edgeStyles: Record<string, LabelStyle>,
  // See note on getEdgeStyle above re: the d3 scale type.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  edgeWidthScale: any,
  edgeWidthProperty?: string | null
): string => {
  const style = getEdgeStyle(edge, edgeStyles, edgeWidthScale, edgeWidthProperty)
  if (style.showLabel === false) return ''

  const field = style.captionField || 'label'
  if (field === 'label') return edge.label

  const fromProperty = edge.properties?.[field]
  if (fromProperty == null) {
    return edge.label
  }
  return safeStringify(fromProperty)
}
