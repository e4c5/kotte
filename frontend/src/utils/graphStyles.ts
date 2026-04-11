import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '../components/GraphView'
import type { LabelStyle } from '../stores/graphStore'

// Color mapping for node labels
const colorScale = d3.scaleOrdinal(d3.schemeCategory10)

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
      const numValue = typeof propValue === 'number' ? propValue : Number.parseFloat(String(propValue))
      if (!Number.isNaN(numValue)) {
        return {
          ...baseStyle,
          size: edgeWidthScale(numValue),
        }
      }
    }
  }
  
  return baseStyle
}

const getDescriptivePropertyValue = (properties: Record<string, unknown>): string | null => {
  const nameKeys = ['name', 'title', 'fqn', 'signature']
  for (const key of nameKeys) {
    const value = properties[key]
    if (value != null && String(value).trim() !== '') {
      return String(value)
    }
  }
  return null
}

const shortenLongIdentifier = (s: string): string => {
  if (s.length > 40 && (s.includes('.') || s.includes('#'))) {
    return s.includes('#') ? s.split('#').pop()! : s.split('.').pop()!
  }
  return s
}

const safeStringify = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (e) {
      return String(value)
    }
  }
  return String(value)
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
    const descriptive = getDescriptivePropertyValue(node.properties as Record<string, unknown>)
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
  return fromProperty != null ? safeStringify(fromProperty) : edge.label
}
