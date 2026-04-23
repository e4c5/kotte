import { describe, expect, it } from 'vitest'
import type { GraphMetadata } from '../services/graph'
import { graphMetadataToEditorSchema } from './cypherSchema'

describe('graphMetadataToEditorSchema', () => {
  it('returns an empty object when metadata is null', () => {
    expect(graphMetadataToEditorSchema(null)).toEqual({})
  })

  it('maps labels, relationship types, and deduped sorted property keys', () => {
    const meta: GraphMetadata = {
      graph_name: 'g',
      node_labels: [
        { label: 'Person', count: 1, properties: ['name', 'age'] },
        { label: '', count: 0, properties: ['x'] },
      ],
      edge_labels: [
        { label: 'KNOWS', count: 1, properties: ['since', 'name'] },
      ],
    }
    expect(graphMetadataToEditorSchema(meta)).toEqual({
      labels: ['Person'],
      relationshipTypes: ['KNOWS'],
      propertyKeys: ['age', 'name', 'since', 'x'],
    })
  })

  it('omits empty schema arrays when there are no keys', () => {
    const meta: GraphMetadata = {
      graph_name: 'empty',
      node_labels: [],
      edge_labels: [],
    }
    expect(graphMetadataToEditorSchema(meta)).toEqual({})
  })
})
