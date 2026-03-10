import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { compareBaskets, type BasketCompareItem } from '@/services/baskets';

type SortKey = 'totalPnlPercent' | 'winRate' | 'avgPnlPercent' | 'maxDrawdown';

function BasketCompare() {
  const [items, setItems] = useState<BasketCompareItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('totalPnlPercent');
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setError('');
      const data = await compareBaskets();
      setItems(data);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDesc(!sortDesc);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  const sorted = [...items].sort((a, b) => {
    const diff = (a[sortKey] ?? 0) - (b[sortKey] ?? 0);
    return sortDesc ? -diff : diff;
  });

  function sortArrow(key: SortKey) {
    if (sortKey !== key) return '';
    return sortDesc ? ' ↓' : ' ↑';
  }

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <header className="hero">
          <div>
            <p className="eyebrow">
              <Link to="/baskets">实盘模拟</Link>{' / '}策略对比
            </p>
            <h1>策略对比</h1>
            <p className="hero-copy">横向对比所有策略篮子的核心收益指标，点击表头排序。</p>
          </div>
          <div className="hero-orb" aria-hidden="true" />
        </header>

        <nav className="nav-bar">
          <Link to="/baskets" className="nav-link">返回列表</Link>
        </nav>

        {error && <div className="state-card error-state">{error}</div>}
        {loading && <div className="state-card">加载中...</div>}
        {!loading && items.length === 0 && <div className="state-card">暂无策略数据。</div>}

        {!loading && sorted.length > 0 && (
          <div className="card" style={{ overflowX: 'auto', padding: '12px 0' }}>
            <table className="compare-table">
              <thead>
                <tr>
                  <th>策略</th>
                  <th>资金</th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('totalPnlPercent')}>
                    收益率{sortArrow('totalPnlPercent')}
                  </th>
                  <th>总盈亏</th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('winRate')}>
                    胜率{sortArrow('winRate')}
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('avgPnlPercent')}>
                    平均收益{sortArrow('avgPnlPercent')}
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('maxDrawdown')}>
                    最大回撤{sortArrow('maxDrawdown')}
                  </th>
                  <th>股票</th>
                  <th>在持/已平</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((item, idx) => (
                  <tr key={item.basketId}>
                    <td className="col-name">
                      <Link to={`/baskets/${item.basketId}`}>
                        {idx === 0 && sortKey === 'totalPnlPercent' && sortDesc ? '🏆 ' : ''}
                        {item.basketName}
                      </Link>
                    </td>
                    <td>{formatMoney(item.capital)}</td>
                    <td className={item.totalPnlPercent >= 0 ? 'positive' : 'negative'} style={{ fontWeight: 700 }}>
                      {(item.totalPnlPercent * 100).toFixed(2)}%
                    </td>
                    <td className={item.totalPnl >= 0 ? 'positive' : 'negative'}>
                      {item.totalPnl >= 0 ? '+' : ''}{item.totalPnl.toFixed(0)}
                    </td>
                    <td>{(item.winRate * 100).toFixed(1)}%</td>
                    <td>{(item.avgPnlPercent * 100).toFixed(2)}%</td>
                    <td>{(item.maxDrawdown * 100).toFixed(2)}%</td>
                    <td>{item.stockCount}</td>
                    <td>{item.openCount} / {item.closedCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Card-based summary for each basket */}
        {!loading && sorted.length > 0 && (
          <div className="detail-stack">
            {sorted.map((item) => (
              <Link key={item.basketId} to={`/baskets/${item.basketId}`} className="basket-card">
                <div className="basket-card-head">
                  <h3>{item.basketName}</h3>
                  <span
                    className={`position-pnl ${item.totalPnlPercent >= 0 ? 'positive' : 'negative'}`}
                    style={{ fontSize: '1.2rem' }}
                  >
                    {(item.totalPnlPercent * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="stat-grid" style={{ marginTop: 12 }}>
                  <div className="stat-box">
                    <span>总盈亏</span>
                    <strong className={item.totalPnl >= 0 ? 'positive' : 'negative'}>
                      {item.totalPnl >= 0 ? '+' : ''}{item.totalPnl.toFixed(0)}
                    </strong>
                  </div>
                  <div className="stat-box">
                    <span>胜率</span>
                    <strong>{(item.winRate * 100).toFixed(1)}%</strong>
                  </div>
                  <div className="stat-box">
                    <span>平均收益</span>
                    <strong>{(item.avgPnlPercent * 100).toFixed(2)}%</strong>
                  </div>
                  <div className="stat-box">
                    <span>最大回撤</span>
                    <strong>{(item.maxDrawdown * 100).toFixed(2)}%</strong>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function formatMoney(value: number) {
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

export default BasketCompare;
