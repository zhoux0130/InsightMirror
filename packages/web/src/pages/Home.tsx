import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { getStockDetail, listStockOptions, type StockDetailResponse, type StockOption } from '@/services/stocks';
import { useAuth } from '@/contexts/AuthContext';

const FAVORITES_KEY = 'insightmirror:favorites';

function Home() {
  const { user, isLoggedIn, logout } = useAuth();
  const [options, setOptions] = useState<StockOption[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [detail, setDetail] = useState<StockDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [favorites, setFavorites] = useState<string[]>(loadFavorites());

  const currentOption = useMemo(
    () => options.find((option) => option.symbol === selectedSymbol) ?? null,
    [options, selectedSymbol]
  );
  const isFavorite = selectedSymbol.length > 0 && favorites.includes(selectedSymbol);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    try {
      setLoading(true);
      setError('');
      const stockOptions = await listStockOptions();
      setOptions(stockOptions);

      if (stockOptions.length === 0) {
        setDetail(null);
        return;
      }

      const first = stockOptions[0];
      setSelectedSymbol(first.symbol);
      setSelectedDate(first.lastTradeDate);
      const payload = await getStockDetail(first.symbol, { endDate: first.lastTradeDate, topK: 100 });
      setDetail(payload);
      setSelectedDate(payload.security.tradeDate);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '加载详情失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleQuery(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!selectedSymbol) {
      return;
    }

    try {
      setLoading(true);
      setError('');
      const payload = await getStockDetail(selectedSymbol, {
        endDate: selectedDate || undefined,
        topK: 100,
      });
      setDetail(payload);
      setSelectedDate(payload.security.tradeDate);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '查询失败');
    } finally {
      setLoading(false);
    }
  }

  function handleSymbolChange(symbol: string) {
    setSelectedSymbol(symbol);
    const option = options.find((item) => item.symbol === symbol);
    if (option) {
      setSelectedDate(option.lastTradeDate);
    }
  }

  function toggleFavorite() {
    if (!selectedSymbol) {
      return;
    }

    const next = favorites.includes(selectedSymbol)
      ? favorites.filter((symbol) => symbol !== selectedSymbol)
      : [...favorites, selectedSymbol];

    setFavorites(next);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
  }

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <header className="hero">
          <div>
            <p className="eyebrow">InsightMirror Demo</p>
            <h1>个股结构诊断</h1>
            <p className="hero-copy">基于 60 日结构窗口、相似样本统计和量价代理信号的单页演示。</p>
          </div>
          <div className="hero-orb" aria-hidden="true" />
        </header>

        <nav className="nav-bar">
          <Link to="/baskets" className="nav-link">实盘模拟</Link>
          <div className="nav-spacer" />
          {isLoggedIn ? (
            <div className="user-bar">
              {user?.avatar ? (
                <img className="user-avatar" src={user.avatar} alt="" />
              ) : (
                <span className="user-avatar-placeholder" />
              )}
              <span className="user-name">{user?.nickname || '用户'}</span>
              <button className="btn btn-ghost btn-xs" onClick={logout}>退出</button>
            </div>
          ) : (
            <Link to="/login" className="nav-link">登录</Link>
          )}
        </nav>

        <form className="query-panel" onSubmit={handleQuery}>
          <label className="field">
            <span>股票</span>
            <select value={selectedSymbol} onChange={(event) => handleSymbolChange(event.target.value)}>
              {options.map((option) => (
                <option key={option.symbol} value={option.symbol}>
                  {option.name} · {option.symbol}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>查询日期</span>
            <input
              type="date"
              value={selectedDate}
              max={currentOption?.lastTradeDate}
              onChange={(event) => setSelectedDate(event.target.value)}
            />
          </label>

          <button className="primary-button" type="submit" disabled={loading || !selectedSymbol}>
            {loading ? '计算中...' : '刷新详情'}
          </button>
        </form>

        {error ? <div className="state-card error-state">{error}</div> : null}

        {!detail && !loading ? <div className="state-card">当前没有可展示的数据。</div> : null}

        {detail ? (
          <div className="detail-stack">
            <section className="card summary-card">
              <div className="summary-head">
                <div>
                  <div className="summary-title-row">
                    <h2>{detail.security.name}</h2>
                    <button
                      className={`favorite-chip ${isFavorite ? 'active' : ''}`}
                      type="button"
                      onClick={toggleFavorite}
                    >
                      {isFavorite ? '已在收藏池' : '加入收藏池'}
                    </button>
                  </div>
                  <p className="summary-meta">
                    {detail.security.symbol} · 截至 {detail.security.tradeDate}
                  </p>
                </div>
                <div className="price-block">
                  <strong>{formatPrice(detail.quote.close)}</strong>
                  <span className={detail.quote.changePct >= 0 ? 'positive' : 'negative'}>
                    {formatSignedPercent(detail.quote.changePct)}
                  </span>
                </div>
              </div>

              <div className="divider" />

              <div className="metric-group">
                <p className="metric-line leading">
                  <span className={`signal-dot rating-${detail.rating.label}`}>●</span>
                  当前评级：<strong>{detail.rating.label}</strong>
                </p>
                <p className="metric-line">结构趋势：{detail.rating.stageTrend}</p>
                <p className="metric-line">主线一致性：{detail.rating.mainlineConsistency}</p>
              </div>
            </section>

            <section className="card card-trio">
              <SectionTitle
                title={detail.entry.mode === 'range' ? '建议参与区间' : '参与建议'}
                badge={`评分 ${detail.rating.score}`}
              />
              {detail.entry.mode === 'range' && detail.entry.lower != null && detail.entry.upper != null ? (
                <>
                  <p className="range-value">
                    {formatPrice(detail.entry.lower)} - {formatPrice(detail.entry.upper)}
                  </p>
                  <p className="metric-line">当前价格：{detail.entry.position}</p>
                  <p className="metric-line">
                    风险失效位：{detail.entry.invalidationLevel == null ? '--' : formatPrice(detail.entry.invalidationLevel)}
                  </p>
                </>
              ) : (
                <>
                  <p className="range-value">暂不参与</p>
                  <p className="metric-line">当前状态：跌破支撑确认区</p>
                  <p className="metric-line">
                    观察位置：{detail.entry.watchLevel == null ? '--' : formatPrice(detail.entry.watchLevel)} 附近
                  </p>
                </>
              )}
              <blockquote>{detail.entry.note}</blockquote>
            </section>

            <section className="card card-trio">
              <SectionTitle title="情绪温度" badge={`${detail.emotion.temp} / 100`} />
              <p className="pill-row">
                <span className="soft-pill">{detail.emotion.status}</span>
              </p>
              <p className="metric-line">
                当前阶段：{detail.emotion.temp >= 80 ? '偏拥挤' : detail.emotion.temp >= 55 ? '健康偏强' : '未过热'}
              </p>
              {detail.emotion.warning ? <p className="metric-line accent-copy">{detail.emotion.warning}</p> : null}
            </section>

            <section className="card card-trio">
              <SectionTitle title="阶段结构" />
              <div className="phase-rail">
                {detail.phase.nodes.map((node) => (
                  <div
                    key={node}
                    className={`phase-node ${detail.phase.activeNode === node ? 'active' : ''}`}
                  >
                    <span className="phase-node-dot" />
                    <span>{node}</span>
                  </div>
                ))}
              </div>
              <div className="phase-foot">
                <p className="metric-line">当前处于：{detail.phase.current}</p>
                <span className={detail.phase.trendBroken ? 'negative' : 'muted-copy'}>
                  {detail.phase.trendNote}
                </span>
              </div>
            </section>

            <section className="card card-duo">
              <SectionTitle title="风险收益结构" badge={`过去 ${detail.riskReward.sampleYears} 年`} />
              <div className="stat-grid">
                <div className="stat-box">
                  <span>上涨概率</span>
                  <strong>{formatPercent(detail.riskReward.upProbability)}</strong>
                </div>
                <div className="stat-box">
                  <span>平均最大回撤</span>
                  <strong>{formatPercent(detail.riskReward.avgMaxDrawdown)}</strong>
                </div>
              </div>
              <p className="metric-line">
                基于 {detail.riskReward.similarCount} 个相似结构样本，Top-K={detail.riskReward.topK}
              </p>
            </section>

            <section className="card card-duo">
              <SectionTitle title="资金延续性" badge={detail.flow.continuity} />
              {detail.flow.signals.map((signal) => (
                <p key={signal} className="metric-line">
                  {signal}
                </p>
              ))}
              <p className="metric-line emphasis">
                延续性分析：3 日内延续概率 {formatPercent(detail.flow.continuationProb3d)}
              </p>
              <blockquote>{detail.flow.quote}</blockquote>
            </section>

            {detail.similarityBreakdown ? (
              <section className="card card-wide">
                <SectionTitle
                  title="相似度拆解"
                  badge={`${detail.similarityBreakdown.windowSize} 日窗口`}
                />
                <p className="metric-line">
                  最相似历史样本：{detail.similarityBreakdown.symbol} · {detail.similarityBreakdown.endDate}
                </p>
                <p className="range-value">{detail.similarityBreakdown.overallScore.toFixed(1)} 分</p>
                <div className="similarity-grid">
                  {detail.similarityBreakdown.dimensions.map((dimension) => (
                    <article className="similarity-item" key={dimension.key}>
                      <div className="similarity-head">
                        <strong>{dimension.label}</strong>
                        <span>{dimension.score.toFixed(1)}</span>
                      </div>
                      <div className="similarity-track">
                        <span
                          className="similarity-fill"
                          style={{ width: `${dimension.score}%` }}
                        />
                      </div>
                      <p>{dimension.description}</p>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="card card-wide">
              <SectionTitle title="相似样本" badge="Top 8" />
              <div className="sample-list">
                {detail.similarSamples.map((sample) => (
                  <article className="sample-row" key={sample.segmentId}>
                    <div>
                      <strong>{sample.symbol}</strong>
                      <p>{sample.endDate}</p>
                    </div>
                    <div className="sample-stats">
                      <span>相似度 {formatPercent(sample.similarity)}</span>
                      <span>5D {formatSignedPercent(sample.return5d * 100)}</span>
                      <span>回撤 {formatPercent(sample.maxDrawdown5d)}</span>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function SectionTitle({ title, badge }: { title: string; badge?: string }) {
  return (
    <div className="section-title">
      <h3>{title}</h3>
      {badge ? <span className="soft-pill">{badge}</span> : null}
    </div>
  );
}

function formatPrice(value: number) {
  return value.toFixed(value >= 100 ? 2 : 2);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatSignedPercent(value: number) {
  const numeric = value > 1 || value < -1 ? value : value;
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}%`;
}

function loadFavorites(): string[] {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default Home;
