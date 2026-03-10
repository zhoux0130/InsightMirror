import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { getWechatLoginUrl } from '@/services/auth';

function Login() {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const [loginUrl, setLoginUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isLoggedIn) {
      navigate('/', { replace: true });
      return;
    }

    getWechatLoginUrl()
      .then(({ url, state }) => {
        setLoginUrl(url);
        sessionStorage.setItem('wx_login_state', state);

        // 尝试内嵌微信二维码（需要微信 JS SDK 加载）
        if (typeof (window as any).WxLogin === 'function') {
          (window as any).WxLogin({
            self_redirect: false,
            id: 'wx-qr-container',
            appid: new URL(url).searchParams.get('appid'),
            scope: 'snsapi_login',
            redirect_uri: encodeURIComponent(
              new URL(url).searchParams.get('redirect_uri') || ''
            ),
            state,
            style: 'black',
            href: '',
          });
        }
      })
      .catch((err) => {
        setError(err?.message || '获取登录链接失败');
      })
      .finally(() => setLoading(false));
  }, [isLoggedIn, navigate]);

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <div className="login-page">
          <div className="login-card card">
            <h2 className="login-title">登录 InsightMirror</h2>
            <p className="login-subtitle">使用微信扫码登录以使用完整功能</p>

            {loading ? (
              <div className="login-loading">加载中...</div>
            ) : error ? (
              <div className="login-error">{error}</div>
            ) : (
              <>
                <div id="wx-qr-container" className="wx-qr-container" />
                {loginUrl && (
                  <a href={loginUrl} className="btn btn-accent login-wx-btn">
                    打开微信扫码登录
                  </a>
                )}
              </>
            )}

            <button className="btn btn-ghost login-back-btn" onClick={() => navigate('/')}>
              返回首页
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

export default Login;
