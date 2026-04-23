/**
 * Package ships types under `src/` but `package.json` "exports" omit them, so
 * TypeScript with `moduleResolution: "bundler"` cannot resolve declarations.
 */
declare module '@neo4j-cypher/codemirror' {
  import type { Extension } from '@codemirror/state'

  export type Theme = 'light' | 'dark' | 'auto'

  export interface CypherMirrorOptions {
    theme?: Theme
    lineNumbers?: boolean
    search?: boolean
    lineWrapping?: boolean
    placeholder?: string
  }

  export interface CypherMirrorExtensionHandlers {
    onFocusChanged?: (focused: boolean) => void
  }

  export function getExtensions(
    options?: CypherMirrorOptions,
    handlers?: CypherMirrorExtensionHandlers
  ): Extension[]
}
