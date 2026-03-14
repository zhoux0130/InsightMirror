import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import Home from './pages/Home';
import BasketList from './pages/BasketList';
import BasketDetail from './pages/BasketDetail';
import BasketCompare from './pages/BasketCompare';
import Login from './pages/Login';
import WechatCallback from './pages/WechatCallback';
import type { ReactNode } from 'react';

function RequireAuth({ children }: { children: ReactNode }) {
  const { isLoggedIn, loading } = useAuth();

  if (loading) {
    return (
      <main className="detail-app">
        <section className="detail-shell">
          <div className="state-card">加载中...</div>
        </section>
      </main>
    );
  }

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth/wechat/callback" element={<WechatCallback />} />
      <Route
        path="/baskets"
        element={
          <RequireAuth>
            <BasketList />
          </RequireAuth>
        }
      />
      <Route
        path="/baskets/compare"
        element={
          <RequireAuth>
            <BasketCompare />
          </RequireAuth>
        }
      />
      <Route
        path="/baskets/:id"
        element={
          <RequireAuth>
            <BasketDetail />
          </RequireAuth>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
