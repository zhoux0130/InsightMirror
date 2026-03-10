import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import {
  listBaskets,
  createBasket,
  deleteBasket,
  type BasketSummary,
} from '@/services/baskets';

function BasketList() {
  const [baskets, setBaskets] = useState<BasketSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formCapital, setFormCapital] = useState('100000');
  const [deleteTarget, setDeleteTarget] = useState<BasketSummary | null>(null);

  useEffect(() => {
    void loadBaskets();
  }, []);

  async function loadBaskets() {
    try {
      setLoading(true);
      setError('');
      const data = await listBaskets();
      setBaskets(data);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!formName.trim()) return;
    try {
      setError('');
      await createBasket({
        name: formName.trim(),
        description: formDesc.trim() || undefined,
        capital: Number(formCapital) || 100000,
      });
      setFormName('');
      setFormDesc('');
      setFormCapital('100000');
      setShowForm(false);
      await loadBaskets();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '创建失败');
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      setError('');
      await deleteBasket(deleteTarget.id);
      setDeleteTarget(null);
      await loadBaskets();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '删除失败');
    }
  }

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <header className="hero">
          <div>
            <p className="eyebrow">InsightMirror</p>
            <h1>实盘模拟</h1>
            <p className="hero-copy">创建策略篮子，关注股票，模拟交易，对比收益。</p>
          </div>
          <div className="hero-orb" aria-hidden="true" />
        </header>

        <nav className="nav-bar">
          <button className="btn btn-accent" onClick={() => setShowForm(!showForm)}>
            {showForm ? '取消' : '+ 创建策略'}
          </button>
          <Link to="/baskets/compare" className="nav-link">策略对比</Link>
          <Link to="/" className="nav-link">个股诊断</Link>
        </nav>

        {showForm && (
          <form className="card" onSubmit={handleCreate}>
            <div className="section-title"><h3>新建策略</h3></div>
            <label className="field">
              <span>策略名称 *</span>
              <input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="如：MA20突破策略"
                required
              />
            </label>
            <label className="field" style={{ marginTop: 8 }}>
              <span>描述</span>
              <input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder="可选：描述策略思路"
              />
            </label>
            <label className="field" style={{ marginTop: 8 }}>
              <span>初始资金</span>
              <input
                type="number"
                value={formCapital}
                onChange={(e) => setFormCapital(e.target.value)}
                min="1000"
                step="1000"
              />
            </label>
            <div style={{ marginTop: 14 }}>
              <button className="btn btn-accent" type="submit">创建</button>
            </div>
          </form>
        )}

        {error && <div className="state-card error-state">{error}</div>}
        {loading && <div className="state-card">加载中...</div>}
        {!loading && baskets.length === 0 && !showForm && (
          <div className="state-card">暂无策略，点击「+ 创建策略」开始。</div>
        )}

        <div className="basket-grid">
          {baskets.map((b) => (
            <Link key={b.id} to={`/baskets/${b.id}`} className="basket-card">
              <div className="basket-card-head">
                <div>
                  <h3>{b.name}</h3>
                  {b.description && <p className="basket-card-desc">{b.description}</p>}
                </div>
                <span className={`status-pill ${b.status === 'active' ? 'status-active' : 'status-archived'}`}>
                  {b.status === 'active' ? '运行中' : '已归档'}
                </span>
              </div>

              <div className="stat-grid" style={{ marginTop: 14 }}>
                <div className="stat-box">
                  <span>资金</span>
                  <strong>{formatMoney(b.capital)}</strong>
                </div>
                <div className="stat-box">
                  <span>关注</span>
                  <strong>{b.stockCount}</strong>
                </div>
                <div className="stat-box">
                  <span>在持</span>
                  <strong>{b.openPositionCount}</strong>
                </div>
                <div className="stat-box">
                  <span>已平仓</span>
                  <strong>{b.closedPositionCount}</strong>
                </div>
              </div>

              <div className="basket-card-foot">
                <button
                  className="btn btn-danger btn-xs"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDeleteTarget(b); }}
                >
                  删除
                </button>
              </div>
            </Link>
          ))}
        </div>

        {deleteTarget && (
          <div className="confirm-overlay" onClick={() => setDeleteTarget(null)}>
            <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
              <h4>确认删除</h4>
              <p>删除策略「{deleteTarget.name}」后，所有关联的关注列表、规则和持仓记录都将被清除，此操作不可撤销。</p>
              <div className="confirm-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => setDeleteTarget(null)}>取消</button>
                <button className="btn btn-danger btn-sm" onClick={confirmDelete}>删除</button>
              </div>
            </div>
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

export default BasketList;
