/**
 * Ordinal color scale for node labels. Matches D3 default so sidebar pills match graph node colors.
 */
const LABEL_COLORS = [
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]

const labelToIndex = new Map<string, number>()
let nextIndex = 0

export function getNodeLabelColor(label: string): string {
  let idx = labelToIndex.get(label)
  if (idx === undefined) {
    idx = nextIndex++
    labelToIndex.set(label, idx)
  }
  return LABEL_COLORS[idx % LABEL_COLORS.length] ?? '#6b7280'
}
