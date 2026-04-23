import type { EditorSupportSchema } from '@neo4j-cypher/editor-support'
import type { GraphMetadata } from '../services/graph'

function sortedPropertyKeysFromMetadata(metadata: GraphMetadata): string[] {
  const keys = new Set<string>()
  for (const n of metadata.node_labels) {
    for (const p of n.properties) {
      if (p) keys.add(p)
    }
  }
  for (const e of metadata.edge_labels) {
    for (const p of e.properties) {
      if (p) keys.add(p)
    }
  }
  return [...keys].sort((a, b) => a.localeCompare(b))
}

/**
 * Maps Kotte graph catalog metadata into Neo4j editor-support schema so the
 * Cypher editor can suggest labels, relationship types, and property keys
 * from the active graph.
 */
export function graphMetadataToEditorSchema(
  metadata: GraphMetadata | null
): EditorSupportSchema {
  if (!metadata) {
    return {}
  }

  const labels = metadata.node_labels.map((n) => n.label).filter(Boolean)
  const relationshipTypes = metadata.edge_labels.map((e) => e.label).filter(Boolean)
  const propertyKeys = sortedPropertyKeysFromMetadata(metadata)

  return {
    ...(labels.length > 0 ? { labels } : {}),
    ...(relationshipTypes.length > 0 ? { relationshipTypes } : {}),
    ...(propertyKeys.length > 0 ? { propertyKeys } : {}),
  }
}
