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
      try {
        const numValue = typeof propValue === 'number' ? propValue : parseFloat(String(propValue))
        if (!isNaN(numValue)) {
          const mappedWidth = edgeWidthScale(numValue)
          return {
            ...baseStyle,
            size: mappedWidth,
          }
        }
      } catch (e) {
        // If mapping fails, use base style
      }
    }
  }
  
  return baseStyle
}

export const getNodeCaption = (
  node: GraphNode,
  nodeStyles: Record<string, LabelStyle>
): string => {
  const style = getNodeStyle(node, nodeStyles)
  if (style.showLabel === false) {
    return ''
  }
  const field = style.captionField || 'label'
  let caption: string
  if (field === 'label') {
    caption = node.label
  } else {
    caption = String(node.properties[field] ?? node.id)
  }
  // If caption is the graph label (e.g. "CodeElement") and we have properties, use a descriptive property
  if (caption === node.label && node.properties && typeof node.properties === 'object') {
    const p = node.properties as Record<string, unknown>
    const name = p.name ?? p.title ?? p.fqn ?? p.signature
    if (name != null && String(name).trim() !== '') {
      const s = String(name)
      // Shorten long FQN/signature: show last segment if longer than 40 chars
      if (s.length > 40 && (s.includes('.') || s.includes('#'))) {
        const last = s.includes('#') ? s.split('#').pop()! : s.split('.').pop()!
        return last
      }
      return s
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
  if (style.showLabel === false) {
    return ''
  }
  const field = style.captionField || 'label'
  if (field === 'label') {
    return edge.label
  }
  const fromProperty = edge.properties?.[field]
  if (fromProperty == null) {
    return edge.label
  }
  return String(fromProperty)
}
