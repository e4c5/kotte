import { useState, useMemo } from 'react'

export interface TableRow {
  data: Record<string, unknown>
}

interface TableViewProps {
  columns: string[]
  rows: TableRow[]
  pageSize?: number
  streaming?: boolean
  onLoadMore?: () => Promise<void>
  hasMore?: boolean
  loadingMore?: boolean
  /** When empty, show this graph name so user can verify they selected the right graph */
  queriedGraph?: string | null
}

export default function TableView({
  columns,
  rows,
  pageSize = 50,
  streaming = false,
  onLoadMore,
  hasMore = false,
  loadingMore = false,
  queriedGraph = null,
}: TableViewProps) {
  const [currentPage, setCurrentPage] = useState(1)

  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    const end = start + pageSize
    return rows.slice(start, end)
  }, [rows, currentPage, pageSize])

  const totalPages = Math.ceil(rows.length / pageSize)

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return 'null'
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2)
    }
    return String(value)
  }

  const exportToCSV = () => {
    const headers = columns.join(',')
    const csvRows = rows.map((row) =>
      columns
        .map((col) => {
          const value = row.data[col]
          const str = formatValue(value)
          // Escape quotes and wrap in quotes if contains comma
          if (str.includes(',') || str.includes('"')) {
            return `"${str.replace(/"/g, '""')}"`
          }
          return str
        })
        .join(',')
    )
    const csv = [headers, ...csvRows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query-results.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportToJSON = () => {
    const json = JSON.stringify(rows.map((r) => r.data), null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query-results.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (rows.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-zinc-400, #a1a1aa)' }}>
        <p style={{ marginBottom: '0.5rem' }}>No rows returned.</p>
        {queriedGraph && (
          <p style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Queried graph: <strong>{queriedGraph}</strong>. If you expected data, select the correct graph in the schema sidebar (e.g. <code style={{ fontSize: '0.8rem' }}>antikythera_graph</code>).
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center px-4 py-3 border-b border-zinc-700 bg-zinc-900/80 text-zinc-300 text-sm">
        <div>
          Showing {paginatedRows.length} of {rows.length} rows
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={exportToCSV}
            className="px-4 py-2 text-sm rounded-lg border border-zinc-600 bg-zinc-700 text-zinc-100 hover:bg-zinc-600 transition-colors"
          >
            Export CSV
          </button>
          <button
            type="button"
            onClick={exportToJSON}
            className="px-4 py-2 text-sm rounded-lg border border-zinc-600 bg-zinc-700 text-zinc-100 hover:bg-zinc-600 transition-colors"
          >
            Export JSON
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }} className="bg-zinc-950">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-zinc-800 border-b-2 border-zinc-600">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2.5 text-left text-sm font-semibold text-zinc-100"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-zinc-100">
            {paginatedRows.map((row, idx) => (
              <tr key={idx} className="border-b border-zinc-700 hover:bg-zinc-800/50">
                {columns.map((col) => (
                  <td
                    key={col}
                    className="px-3 py-2.5 font-mono text-sm text-zinc-200"
                  >
                    {formatValue(row.data[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {streaming && hasMore && onLoadMore ? (
        <div className="flex justify-center items-center px-4 py-3 border-t border-zinc-700 bg-zinc-900/80">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loadingMore}
            className="px-4 py-2 rounded-lg border border-zinc-600 bg-zinc-700 text-zinc-100 hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loadingMore ? 'Loading...' : 'Load More'}
          </button>
        </div>
      ) : totalPages > 1 ? (
        <div className="flex justify-center gap-2 items-center px-4 py-3 border-t border-zinc-700 bg-zinc-900/80 text-zinc-300 text-sm">
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-4 py-2 rounded-lg border border-zinc-600 bg-zinc-700 text-zinc-100 hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-zinc-700 transition-colors"
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="px-4 py-2 rounded-lg border border-zinc-600 bg-zinc-700 text-zinc-100 hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-zinc-700 transition-colors"
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  )
}

