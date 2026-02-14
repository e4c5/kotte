import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ConnectionPage from './pages/ConnectionPage'
import WorkspacePage from './pages/WorkspacePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<ConnectionPage />} />
          <Route path="workspace" element={<WorkspacePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

