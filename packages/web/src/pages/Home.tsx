import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

function Home() {
  const { isLoggedIn, user, logout } = useAuth()

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <nav className="nav-bar">
          <Link to="/" className="nav-link">首页</Link>
          {isLoggedIn ? (
            <>
              <Link to="/posts" className="nav-link">Posts</Link>
              <div className="nav-spacer" />
              <div className="user-bar">
                <span className="user-name">{user?.nickname || '用户'}</span>
                <button className="btn btn-ghost btn-xs" onClick={logout}>退出</button>
              </div>
            </>
          ) : (
            <>
              <div className="nav-spacer" />
              <Link to="/login" className="nav-link">登录</Link>
            </>
          )}
        </nav>

        <header className="hero">
          <div>
            <p className="eyebrow">ecp-vision</p>
            <h1>通用 Web 脚手架</h1>
            <p className="hero-copy">Fastify + Prisma + PostgreSQL + React + Vite 的轻量 Web 应用骨架。</p>
          </div>
          <div className="hero-orb" aria-hidden="true" />
        </header>

        <div className="content">
          <section className="card">
            <h2>快速开始</h2>
            <ul className="feature-list">
              <li>基于 Session Token 的用户认证</li>
              <li>受保护路由自动跳转</li>
              <li>Posts CRUD 示例页面</li>
              <li>React + Vite 前端</li>
            </ul>

            <div className="card-actions">
              {isLoggedIn ? (
                <Link to="/posts" className="btn btn-accent">进入 Posts</Link>
              ) : (
                <Link to="/login" className="btn btn-accent">登录 / 注册</Link>
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  )
}

export default Home
