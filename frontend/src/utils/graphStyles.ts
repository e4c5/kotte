import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '../components/GraphView'
import type { LabelStyle } from '../stores/graphStore'

// Color mapping for node labels
const colorScale = d3.scaleOrdinal(d3.schemeCategory10)

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

export function getDefaultNodeColor(label: string): string {
  return colorScale(label) || '#999'
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
  edgeWidthScale: any,
  edgeWidthProperty?: string
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
  edgeWidthScale: any,
  edgeWidthProperty?: string
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
