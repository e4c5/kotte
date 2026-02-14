import { useState, useMemo } from 'react'

export interface TableRow {
  data: Record<string, unknown>
}

interface TableViewProps {
  columns: string[]
  rows: TableRow[]
  pageSize?: number
}

export default function TableView({
  columns,
  rows,
  pageSize = 50,
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
    return <div style={{ padding: '2rem', textAlign: 'center' }}>No data to display</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid #ccc', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          Showing {paginatedRows.length} of {rows.length} rows
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={exportToCSV}
            style={{
              padding: '0.5rem 1rem',
              fontSize: '0.9rem',
              cursor: 'pointer',
              border: '1px solid #ccc',
              borderRadius: '4px',
              backgroundColor: 'white',
            }}
          >
            Export CSV
          </button>
          <button
            onClick={exportToJSON}
            style={{
              padding: '0.5rem 1rem',
              fontSize: '0.9rem',
              cursor: 'pointer',
              border: '1px solid #ccc',
              borderRadius: '4px',
              backgroundColor: 'white',
            }}
          >
            Export JSON
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f5f5f5', zIndex: 1 }}>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  style={{
                    padding: '0.75rem',
                    textAlign: 'left',
                    borderBottom: '2px solid #ddd',
                    fontWeight: 'bold',
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.map((row, idx) => (
              <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
                {columns.map((col) => (
                  <td
                    key={col}
                    style={{
                      padding: '0.75rem',
                      fontFamily: 'monospace',
                      fontSize: '0.9rem',
                    }}
                  >
                    {formatValue(row.data[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div style={{ padding: '1rem', borderTop: '1px solid #ccc', display: 'flex', justifyContent: 'center', gap: '0.5rem', alignItems: 'center' }}>
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            style={{
              padding: '0.5rem 1rem',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
              border: '1px solid #ccc',
              borderRadius: '4px',
              backgroundColor: 'white',
              opacity: currentPage === 1 ? 0.5 : 1,
            }}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: '0.5rem 1rem',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
              border: '1px solid #ccc',
              borderRadius: '4px',
              backgroundColor: 'white',
              opacity: currentPage === totalPages ? 0.5 : 1,
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

