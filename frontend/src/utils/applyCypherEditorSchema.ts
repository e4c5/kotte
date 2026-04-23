import type { EditorView } from '@codemirror/view'
import type { EditorSupportSchema } from '@neo4j-cypher/editor-support'
import { getStateEditorSupport } from 'neo4j-cypher-cm-state-selectors'

/**
 * Pushes catalog schema into the Neo4j Cypher editor-support instance held in
 * CodeMirror state. Resolved via `vite.config.ts` alias (the package omits
 * this path from `exports`).
 */
export function applyCypherEditorSchema(
  view: EditorView,
  schema: EditorSupportSchema
): void {
  const support = getStateEditorSupport(view.state)
  support?.setSchema(schema)
}
