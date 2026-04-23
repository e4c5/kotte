declare module 'neo4j-cypher-cm-state-selectors' {
  import type { EditorState } from '@codemirror/state'
  import type { CypherEditorSupport } from '@neo4j-cypher/editor-support'

  export function getStateEditorSupport(state: EditorState): CypherEditorSupport | null
}
