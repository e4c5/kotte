import { Outlet, useLocation } from 'react-router-dom'

export default function Layout() {
  const { pathname } = useLocation()
  const isWorkspaceRoute = pathname.startsWith('/workspace')

  if (isWorkspaceRoute) {
    return <Outlet />
  }

  return (
    <div style={{ width: '100%', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{ padding: '1rem', borderBottom: '1px solid #333' }}>
        <h1>Kotte - Apache AGE Visualizer</h1>
      </header>
      <main style={{ flex: 1 }}>
        <Outlet />
      </main>
    </div>
  )
}
