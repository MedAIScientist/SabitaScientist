import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { ThemeProvider } from './theme'
import { api } from './api'
import { Login } from './pages/Login'
import { Projects } from './pages/Projects'
import { Board } from './pages/Board'
import { ExperimentsPage } from './pages/ExperimentsPage'
import { ProfilePage } from './pages/ProfilePage'
import { Setup } from './pages/Setup'

const queryClient = new QueryClient()

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)

  useEffect(() => {
    api.setupStatus().then(r => setNeedsSetup(r.needs_setup)).catch(() => setNeedsSetup(false))
  }, [])

  if (needsSetup === null) return <p style={{ padding: 24 }}>Loading\u2026</p>

  return (
    <BrowserRouter>
      <Routes>
        {needsSetup && <Route path="*" element={<Setup />} />}
        <Route path="/login" element={<Login />} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><Board /></PrivateRoute>} />
        <Route path="/projects/:id/experiments" element={<PrivateRoute><ExperimentsPage /></PrivateRoute>} />
        <Route path="/profile" element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
        {!needsSetup && <Route path="*" element={<Navigate to="/projects" replace />} />}
      </Routes>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
