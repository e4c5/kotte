import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const ConnectionPage = lazy(() => import('./pages/ConnectionPage'))
const WorkspacePage = lazy(() => import('./pages/WorkspacePage'))

const LoadingFallback = () => (
  <div className="flex h-screen w-screen items-center justify-center bg-zinc-950 text-zinc-400">
    <div className="flex flex-col items-center gap-4">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-800 border-t-blue-500" />
      <p className="text-sm font-medium animate-pulse">Loading Kotte...</p>
    </div>
  </div>
)

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<ConnectionPage />} />
            <Route path="workspace" element={<WorkspacePage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
