import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { register, loginByPassword } from '@/services/auth';

type Mode = 'login' | 'register';

function Login() {
  const { isLoggedIn, login } = useAuth();
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
        <div className="login-page">
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
