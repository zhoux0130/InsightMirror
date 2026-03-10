import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { wechatCallback } from '@/services/auth';

function WechatCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code || !state) {
      setError('缺少授权参数');
      return;
    }

    const savedState = sessionStorage.getItem('wx_login_state');
    if (savedState && savedState !== state) {
      setError('状态验证失败，请重新登录');
      return;
    }

    wechatCallback(code, state)
      .then(({ token, user }) => {
        sessionStorage.removeItem('wx_login_state');
        login(token, user);
        navigate('/', { replace: true });
      })
      .catch((err) => {
        setError(err?.response?.data?.error || err?.message || '登录失败');
      });
  }, [searchParams, login, navigate]);

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <div className="login-page">
          <div className="login-card card">
            {error ? (
              <>
                <h2 className="login-title">登录失败</h2>
                <p className="login-error">{error}</p>
                <button className="btn btn-accent" onClick={() => navigate('/login')}>
                  重新登录
                </button>
              </>
            ) : (
              <>
                <h2 className="login-title">登录中...</h2>
                <p className="login-subtitle">正在完成微信授权，请稍候</p>
              </>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

export default WechatCallback;
