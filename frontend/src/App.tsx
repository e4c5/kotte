import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import { LazyRouteErrorBoundary } from './components/LazyRouteErrorBoundary'
import { useTheme } from './utils/useTheme'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const ConnectionPage = lazy(() => import('./pages/ConnectionPage'))
const WorkspacePage = lazy(() => import('./pages/WorkspacePage'))

const LoadingFallback = () => (
  <div className="flex h-screen w-screen items-center justify-center bg-white text-zinc-600 dark:bg-zinc-950 dark:text-zinc-400">
    <div className="flex flex-col items-center gap-4">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-200 border-t-blue-500 dark:border-zinc-800" />
      <p className="text-sm font-medium animate-pulse">Loading Kotte...</p>
    </div>
  </div>
)

function App() {
  // ROADMAP A1: keep Tailwind's `dark` class on <html> in sync with the
  // persisted theme. Mounted at the App root so all routes (login, connection,
  // workspace) pick up the user's preference without a reload.
  useTheme()

  return (
    <BrowserRouter>
      <LazyRouteErrorBoundary>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Layout />}>
              <Route index element={<ConnectionPage />} />
              <Route path="workspace" element={<WorkspacePage />} />
            </Route>
          </Routes>
        </Suspense>
      </LazyRouteErrorBoundary>
    </BrowserRouter>
  )
}

export default App
