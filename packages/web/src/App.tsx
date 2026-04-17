import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import Home from './pages/Home'
import Posts from './pages/Posts'
import Login from './pages/Login'
import type { ReactNode } from 'react'

function RequireAuth({ children }: { children: ReactNode }) {
  const { isLoggedIn, loading } = useAuth()

  if (loading) {
    return (
      <main className="detail-app">
        <section className="detail-shell">
          <div className="state-card">加载中...</div>
        </section>
      </main>
    )
  }

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route
        path="/posts"
        element={
          <RequireAuth>
            <Posts />
          </RequireAuth>
        }
      />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
