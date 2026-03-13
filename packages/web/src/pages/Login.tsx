import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { register, loginByPassword } from '@/services/auth';

type Mode = 'login' | 'register';

function Login() {
  const { isLoggedIn, login } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [nickname, setNickname] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isLoggedIn) {
      navigate('/', { replace: true });
    }
  }, [isLoggedIn, navigate]);

  function switchMode(next: Mode) {
    setMode(next);
    setError('');
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');

    if (!username || !password) {
      setError('请输入用户名和密码');
      return;
    }

    if (mode === 'register') {
      if (username.length < 3) {
        setError('用户名至少 3 个字符');
        return;
      }
      if (password.length < 6) {
        setError('密码至少 6 个字符');
        return;
      }
      if (password !== confirmPassword) {
        setError('两次密码输入不一致');
        return;
      }
    }

    try {
      setSubmitting(true);
      const result =
        mode === 'register'
          ? await register(username, password, nickname || undefined)
          : await loginByPassword(username, password);
      login(result.token, result.user);
      navigate('/', { replace: true });
    } catch (err: any) {
      const msg = err?.response?.data?.error || err?.message || (mode === 'register' ? '注册失败' : '登录失败');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <div className="login-page" style={{ position: 'relative' }}>
          <button className="theme-toggle" onClick={toggleTheme} aria-label="切换主题" style={{ position: 'absolute', top: 0, right: 0 }}>
            {theme === 'light' ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
            )}
          </button>
          <div className="login-card card">
            <h2 className="login-title">
              {mode === 'login' ? '登录 InsightMirror' : '注册 InsightMirror'}
            </h2>
            <p className="login-subtitle">
              {mode === 'login' ? '登录以使用完整功能' : '创建账号以使用完整功能'}
            </p>

            {error ? <div className="login-error">{error}</div> : null}

            <form className="login-form" onSubmit={handleSubmit}>
              <label className="login-field">
                <span>用户名</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  autoComplete="username"
                />
              </label>

              <label className="login-field">
                <span>密码</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
              </label>

              {mode === 'register' ? (
                <>
                  <label className="login-field">
                    <span>确认密码</span>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="再次输入密码"
                      autoComplete="new-password"
                    />
                  </label>

                  <label className="login-field">
                    <span>昵称（可选）</span>
                    <input
                      type="text"
                      value={nickname}
                      onChange={(e) => setNickname(e.target.value)}
                      placeholder="设置你的昵称"
                    />
                  </label>
                </>
              ) : null}

              <button className="btn btn-accent login-submit" type="submit" disabled={submitting}>
                {submitting ? '请稍候...' : mode === 'login' ? '登录' : '注册'}
              </button>
            </form>

            <div className="login-switch">
              {mode === 'login' ? (
                <span>
                  没有账号？
                  <button type="button" onClick={() => switchMode('register')}>
                    注册
                  </button>
                </span>
              ) : (
                <span>
                  已有账号？
                  <button type="button" onClick={() => switchMode('login')}>
                    登录
                  </button>
                </span>
              )}
            </div>

            <div className="login-divider">
              <span>或</span>
            </div>

            <button
              className="btn btn-ghost login-back-btn"
              type="button"
              onClick={() => navigate('/login?wx=1')}
            >
              微信扫码登录
            </button>

            <button
              className="btn btn-ghost login-back-btn"
              type="button"
              onClick={() => navigate('/')}
            >
              返回首页
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

export default Login;
