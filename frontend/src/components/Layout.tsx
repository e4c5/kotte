import { Outlet, useLocation } from 'react-router-dom'

export default function Layout() {
  const { pathname } = useLocation()
  const isWorkspaceRoute = pathname.startsWith('/workspace')

  if (isWorkspaceRoute) {
    return <Outlet />
  }

  return (
    <div className="min-h-screen w-full flex flex-col bg-zinc-950 text-zinc-100">
      <header className="shrink-0 px-4 py-3 border-b border-zinc-800 bg-zinc-900/95">
        <h1 className="text-lg font-semibold text-zinc-100">Kotte — Apache AGE Visualizer</h1>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}
