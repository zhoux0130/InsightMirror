import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getBasket,
  addStock,
  removeStock,
  createRule,
  updateRule,
  deleteRule,
  buyPosition,
  sellPosition,
  getBasketPnl,
  scanRules,
  updateBasket,
  type BasketDetail as BasketDetailType,
  type BasketPnL,
  type ScanResult,
  type ConditionGroup,
  type Condition,
} from '@/services/baskets';

type Tab = 'stocks' | 'rules' | 'positions' | 'pnl';

const INDICATOR_OPTIONS = [
  { value: 'price_vs_ma20', label: '价格偏离MA20 (%)' },
  { value: 'price_vs_ma60', label: '价格偏离MA60 (%)' },
  { value: 'volume_ratio_5d', label: '量比(5日)' },
  { value: 'pct_change', label: '涨跌幅 (%)' },
  { value: 'emotion_temp', label: '情绪温度' },
  { value: 'rating_score', label: '评分' },
  { value: 'up_probability', label: '上涨概率 (%)' },
  { value: 'avg_max_drawdown', label: '平均最大回撤 (%)' },
];

const OP_OPTIONS = ['>', '<', '>=', '<=', '==', '!='];

function indicatorLabel(key: string) {
  return INDICATOR_OPTIONS.find((o) => o.value === key)?.label ?? key;
}

function BasketDetail() {
  const { id } = useParams<{ id: string }>();
  const [basket, setBasket] = useState<BasketDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('stocks');

  // PnL
  const [pnl, setPnl] = useState<BasketPnL | null>(null);
  const [pnlLoading, setPnlLoading] = useState(false);

  // Scan
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [scanning, setScanning] = useState(false);

  // Stock form
  const [newSymbol, setNewSymbol] = useState('');

  // Buy form
  const [buySymbol, setBuySymbol] = useState('');
  const [buyDate, setBuyDate] = useState(todayStr());
  const [buyPrice, setBuyPrice] = useState('');
  const [buyShares, setBuyShares] = useState('');

  // Sell form
  const [sellPosId, setSellPosId] = useState('');
  const [sellDate, setSellDate] = useState(todayStr());
  const [sellPrice, setSellPrice] = useState('');

  // Rule editor
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleName, setRuleName] = useState('');
  const [ruleOperator, setRuleOperator] = useState<'AND' | 'OR'>('AND');
  const [ruleConditions, setRuleConditions] = useState<Condition[]>([
    { type: 'fact', indicator: 'price_vs_ma20', op: '>', value: 0 },
  ]);

  // Edit basket
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editCapital, setEditCapital] = useState('');

  useEffect(() => {
    if (id) void loadBasket();
  }, [id]);

  async function loadBasket() {
    try {
      setLoading(true);
      setError('');
      const data = await getBasket(id!);
      setBasket(data);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function loadPnl() {
    try {
      setPnlLoading(true);
      const data = await getBasketPnl(id!);
      setPnl(data);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '加载收益失败');
    } finally {
      setPnlLoading(false);
    }
  }

  function clearError() { setError(''); }

  // ── Stock handlers ──
  async function handleAddStock() {
    if (!newSymbol.trim()) return;
    try {
      clearError();
      await addStock(id!, newSymbol.trim().toUpperCase());
      setNewSymbol('');
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '添加失败');
    }
  }

  async function handleRemoveStock(symbol: string) {
    try {
      clearError();
      await removeStock(id!, symbol);
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '移除失败');
    }
  }

  // ── Buy / Sell ──
  async function handleBuy() {
    if (!buySymbol) return;
    try {
      clearError();
      await buyPosition(id!, {
        symbol: buySymbol,
        buyDate,
        buyPrice: buyPrice ? Number(buyPrice) : undefined,
        shares: buyShares ? Number(buyShares) : undefined,
      });
      setBuySymbol('');
      setBuyPrice('');
      setBuyShares('');
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '买入失败');
    }
  }

  async function handleSell() {
    if (!sellPosId) return;
    try {
      clearError();
      await sellPosition(id!, sellPosId, {
        sellDate,
        sellPrice: sellPrice ? Number(sellPrice) : undefined,
      });
      setSellPosId('');
      setSellPrice('');
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '卖出失败');
    }
  }

  // ── Rules ──
  async function handleCreateRule() {
    try {
      clearError();
      await createRule(id!, {
        name: ruleName || undefined,
        conditionGroup: { operator: ruleOperator, conditions: ruleConditions },
      });
      setShowRuleForm(false);
      setRuleName('');
      setRuleConditions([{ type: 'fact', indicator: 'price_vs_ma20', op: '>', value: 0 }]);
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '创建规则失败');
    }
  }

  async function handleToggleRule(ruleId: string, enabled: boolean) {
    try {
      clearError();
      await updateRule(id!, ruleId, { enabled: !enabled });
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '更新失败');
    }
  }

  async function handleDeleteRule(ruleId: string) {
    try {
      clearError();
      await deleteRule(id!, ruleId);
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '删除失败');
    }
  }

  // ── Scan ──
  async function handleScan() {
    try {
      clearError();
      setScanning(true);
      const data = await scanRules(id!);
      setScanResults(data);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '扫描失败');
    } finally {
      setScanning(false);
    }
  }

  // ── Edit basket ──
  function startEdit() {
    if (!basket) return;
    setEditName(basket.name);
    setEditDesc(basket.description ?? '');
    setEditCapital(String(basket.capital));
    setEditing(true);
  }

  async function handleSaveEdit() {
    try {
      clearError();
      await updateBasket(id!, {
        name: editName,
        description: editDesc || undefined,
        capital: Number(editCapital) || undefined,
      });
      setEditing(false);
      await loadBasket();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '更新失败');
    }
  }

  // ── Condition helpers ──
  function addCondition() {
    setRuleConditions([...ruleConditions, { type: 'fact', indicator: 'price_vs_ma20', op: '>', value: 0 }]);
  }

  function removeCondition(index: number) {
    setRuleConditions(ruleConditions.filter((_, i) => i !== index));
  }

  function setCondField(index: number, field: keyof Condition, value: any) {
    setRuleConditions(ruleConditions.map((c, i) => i === index ? { ...c, [field]: value } : c));
  }

  // ── Derived ──
  const triggeredSymbols = new Set(scanResults.filter((r) => r.triggered).map((r) => r.symbol));

  if (loading) {
    return (
      <main className="detail-app">
        <section className="detail-shell">
          <div className="state-card">加载中...</div>
        </section>
      </main>
    );
  }

  if (!basket) {
    return (
      <main className="detail-app">
        <section className="detail-shell">
          <div className="state-card error-state">{error || '篮子不存在'}</div>
          <nav className="nav-bar" style={{ marginTop: 12 }}>
            <Link to="/baskets" className="nav-link">返回列表</Link>
          </nav>
        </section>
      </main>
    );
  }

  const openPositions = basket.positions.filter((p) => !p.sellDate);
  const closedPositions = basket.positions.filter((p) => p.sellDate);

  return (
    <main className="detail-app">
      <section className="detail-shell">
        {/* ── Header ── */}
        <header className="hero">
          <div>
            <p className="eyebrow">
              <Link to="/baskets">实盘模拟</Link>{' / '}{basket.name}
            </p>
            <h1>{basket.name}</h1>
            {basket.description && <p className="hero-copy">{basket.description}</p>}
          </div>
          <div className="hero-orb" aria-hidden="true" />
        </header>

        {/* ── Summary bar ── */}
        <div className="card summary-card">
          <div className="stat-grid">
            <div className="stat-box">
              <span>总资金</span>
              <strong>{formatMoney(basket.capital)}</strong>
            </div>
            <div className="stat-box">
              <span>关注</span>
              <strong>{basket.stocks.length}</strong>
            </div>
            <div className="stat-box">
              <span>在持</span>
              <strong>{openPositions.length}</strong>
            </div>
            <div className="stat-box">
              <span>已平仓</span>
              <strong>{closedPositions.length}</strong>
            </div>
          </div>
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-ghost btn-xs" onClick={startEdit}>编辑策略</button>
          </div>
        </div>

        {/* ── Edit dialog ── */}
        {editing && (
          <div className="confirm-overlay" onClick={() => setEditing(false)}>
            <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
              <h4>编辑策略</h4>
              <label className="field">
                <span>名称</span>
                <input value={editName} onChange={(e) => setEditName(e.target.value)} />
              </label>
              <label className="field" style={{ marginTop: 8 }}>
                <span>描述</span>
                <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
              </label>
              <label className="field" style={{ marginTop: 8 }}>
                <span>资金</span>
                <input type="number" value={editCapital} onChange={(e) => setEditCapital(e.target.value)} />
              </label>
              <div className="confirm-actions" style={{ marginTop: 16 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>取消</button>
                <button className="btn btn-accent btn-sm" onClick={handleSaveEdit}>保存</button>
              </div>
            </div>
          </div>
        )}

        {error && <div className="state-card error-state">{error}</div>}

        {/* ── Tabs ── */}
        <div className="tab-bar">
          {(['stocks', 'rules', 'positions', 'pnl'] as Tab[]).map((t) => (
            <button
              key={t}
              className={`tab-item ${tab === t ? 'active' : ''}`}
              onClick={() => { setTab(t); if (t === 'pnl') void loadPnl(); }}
            >
              {{ stocks: '关注列表', rules: '规则管理', positions: '持仓', pnl: '收益' }[t]}
            </button>
          ))}
        </div>

        {/* ══════════ Stocks Tab ══════════ */}
        {tab === 'stocks' && (
          <div className="detail-stack">
            <div className="card">
              <div className="section-title">
                <h3>关注列表</h3>
                <button
                  className="btn btn-accent btn-sm"
                  onClick={handleScan}
                  disabled={scanning || basket.rules.length === 0}
                >
                  {scanning ? '扫描中...' : '扫描规则'}
                </button>
              </div>

              <div className="form-row" style={{ marginBottom: 16 }}>
                <label className="field">
                  <span>股票代码</span>
                  <input
                    value={newSymbol}
                    onChange={(e) => setNewSymbol(e.target.value)}
                    placeholder="如 000001.SZ"
                    onKeyDown={(e) => e.key === 'Enter' && handleAddStock()}
                  />
                </label>
                <button className="btn btn-accent" onClick={handleAddStock}>添加</button>
              </div>

              {basket.stocks.length === 0 ? (
                <p className="empty-hint">暂无关注股票，输入代码添加</p>
              ) : (
                basket.stocks.map((s) => (
                  <div
                    key={s.id}
                    className={`watchlist-item ${triggeredSymbols.has(s.symbol) ? 'triggered-row' : ''}`}
                  >
                    <div>
                      <span className="watchlist-symbol">{s.symbol}</span>
                      {triggeredSymbols.has(s.symbol) && <span className="trigger-badge">触发</span>}
                    </div>
                    <button className="btn btn-danger btn-xs" onClick={() => handleRemoveStock(s.symbol)}>
                      移除
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Scan results */}
            {scanResults.length > 0 && (
              <div className="card">
                <div className="section-title"><h3>扫描结果</h3></div>
                {scanResults.map((r, i) => (
                  <div className="watchlist-item" key={i}>
                    <div>
                      <span className="watchlist-symbol">{r.symbol}</span>
                      <span className="metric-line" style={{ marginLeft: 8 }}>{r.ruleName || '未命名'}</span>
                      <div className="scan-detail-row">
                        {Object.entries(r.details).map(([key, d]) => (
                          <span key={key} className={`scan-tag ${d.passed ? 'scan-tag-pass' : 'scan-tag-fail'}`}>
                            {indicatorLabel(key)} = {d.value.toFixed(2)}
                          </span>
                        ))}
                      </div>
                    </div>
                    <span className={r.triggered ? 'positive' : 'muted-copy'} style={{ fontWeight: 700, fontSize: '0.85rem' }}>
                      {r.triggered ? '触发' : '未触发'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ══════════ Rules Tab ══════════ */}
        {tab === 'rules' && (
          <div className="detail-stack">
            <div className="card">
              <div className="section-title">
                <h3>规则管理</h3>
                <button className="btn btn-accent btn-sm" onClick={() => setShowRuleForm(!showRuleForm)}>
                  {showRuleForm ? '取消' : '+ 规则'}
                </button>
              </div>

              {showRuleForm && (
                <div className="rule-editor">
                  <label className="field">
                    <span>规则名称</span>
                    <input value={ruleName} onChange={(e) => setRuleName(e.target.value)} placeholder="如：情绪高温回避" />
                  </label>
                  <label className="field" style={{ marginTop: 8 }}>
                    <span>逻辑关系</span>
                    <select value={ruleOperator} onChange={(e) => setRuleOperator(e.target.value as 'AND' | 'OR')}>
                      <option value="AND">AND（全部满足）</option>
                      <option value="OR">OR（任一满足）</option>
                    </select>
                  </label>

                  {ruleConditions.map((cond, idx) => (
                    <div className="condition-row" key={idx}>
                      <select
                        className="condition-indicator"
                        value={cond.indicator}
                        onChange={(e) => setCondField(idx, 'indicator', e.target.value)}
                      >
                        {INDICATOR_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                      <select
                        className="condition-op"
                        value={cond.op}
                        onChange={(e) => setCondField(idx, 'op', e.target.value)}
                      >
                        {OP_OPTIONS.map((op) => <option key={op} value={op}>{op}</option>)}
                      </select>
                      <input
                        className="condition-value"
                        type="number"
                        value={cond.value}
                        onChange={(e) => setCondField(idx, 'value', Number(e.target.value))}
                      />
                      <select
                        className="condition-type"
                        value={cond.type}
                        onChange={(e) => setCondField(idx, 'type', e.target.value)}
                      >
                        <option value="fact">行情</option>
                        <option value="computed">计算</option>
                      </select>
                      {ruleConditions.length > 1 && (
                        <button className="btn btn-danger btn-xs" onClick={() => removeCondition(idx)}>X</button>
                      )}
                    </div>
                  ))}

                  <div className="nav-bar" style={{ marginTop: 12 }}>
                    <button className="btn btn-ghost btn-sm" onClick={addCondition}>+ 条件</button>
                    <button className="btn btn-accent btn-sm" onClick={handleCreateRule}>保存规则</button>
                  </div>
                </div>
              )}

              {basket.rules.length === 0 ? (
                <p className="empty-hint">暂无规则，点击「+ 规则」添加</p>
              ) : (
                basket.rules.map((r) => {
                  const cg = r.conditionGroup as ConditionGroup;
                  return (
                    <div className="rule-item" key={r.id}>
                      <div className="rule-head">
                        <span className="rule-name">{r.name || '未命名规则'}</span>
                        <div className="rule-actions">
                          <button
                            className={`toggle-btn ${r.enabled ? 'toggle-on' : 'toggle-off'}`}
                            onClick={() => handleToggleRule(r.id, r.enabled)}
                          >
                            {r.enabled ? '已启用' : '已禁用'}
                          </button>
                          <button className="btn btn-danger btn-xs" onClick={() => handleDeleteRule(r.id)}>
                            删除
                          </button>
                        </div>
                      </div>
                      <p className="rule-expr">
                        {cg.conditions
                          .map((c) => `${indicatorLabel(c.indicator)} ${c.op} ${c.value}`)
                          .join(cg.operator === 'AND' ? ' && ' : ' || ')}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* ══════════ Positions Tab ══════════ */}
        {tab === 'positions' && (
          <div className="detail-stack">
            {/* Buy form */}
            <div className="card">
              <div className="section-title"><h3>买入</h3></div>
              <div className="form-row">
                <label className="field" style={{ flex: 2 }}>
                  <span>股票</span>
                  <select value={buySymbol} onChange={(e) => setBuySymbol(e.target.value)}>
                    <option value="">选择股票</option>
                    {basket.stocks.map((s) => <option key={s.id} value={s.symbol}>{s.symbol}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>日期</span>
                  <input type="date" value={buyDate} onChange={(e) => setBuyDate(e.target.value)} />
                </label>
                <label className="field">
                  <span>价格</span>
                  <input type="number" step="0.01" placeholder="默认收盘价" value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)} />
                </label>
                <label className="field">
                  <span>股数</span>
                  <input type="number" step="100" placeholder="默认等权" value={buyShares} onChange={(e) => setBuyShares(e.target.value)} />
                </label>
                <button className="btn btn-accent" onClick={handleBuy} disabled={!buySymbol}>买入</button>
              </div>
            </div>

            {/* Sell form */}
            {openPositions.length > 0 && (
              <div className="card">
                <div className="section-title"><h3>卖出</h3></div>
                <div className="form-row">
                  <label className="field" style={{ flex: 2 }}>
                    <span>持仓</span>
                    <select value={sellPosId} onChange={(e) => setSellPosId(e.target.value)}>
                      <option value="">选择持仓</option>
                      {openPositions.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.symbol} {p.buyDate} {p.shares}股 @ {p.buyPrice}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>日期</span>
                    <input type="date" value={sellDate} onChange={(e) => setSellDate(e.target.value)} />
                  </label>
                  <label className="field">
                    <span>价格</span>
                    <input type="number" step="0.01" placeholder="默认收盘价" value={sellPrice} onChange={(e) => setSellPrice(e.target.value)} />
                  </label>
                  <button className="btn btn-accent" onClick={handleSell} disabled={!sellPosId}>卖出</button>
                </div>
              </div>
            )}

            {/* Open positions */}
            <div className="card">
              <div className="section-title"><h3>在持仓位</h3></div>
              {openPositions.length === 0 ? (
                <p className="empty-hint">暂无在持仓位</p>
              ) : (
                openPositions.map((p) => (
                  <div className="position-row" key={p.id}>
                    <div className="position-info">
                      <strong>{p.symbol}</strong>
                      <p className="position-meta">
                        {p.buyDate} | {p.shares}股 @ {p.buyPrice.toFixed(2)}
                        {p.note && ` | ${p.note}`}
                      </p>
                    </div>
                    <span className="soft-pill" style={{ fontSize: '0.78rem', minHeight: 26 }}>
                      {p.triggerType === 'rule' ? '规则' : '手动'}
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* Closed positions */}
            <div className="card">
              <div className="section-title"><h3>已平仓</h3></div>
              {closedPositions.length === 0 ? (
                <p className="empty-hint">暂无已平仓位</p>
              ) : (
                closedPositions.map((p) => {
                  const ret = p.sellPrice && p.buyPrice ? (p.sellPrice - p.buyPrice) / p.buyPrice : 0;
                  return (
                    <div className="position-row" key={p.id}>
                      <div className="position-info">
                        <strong>{p.symbol}</strong>
                        <p className="position-meta">
                          {p.buyDate} @ {p.buyPrice.toFixed(2)} → {p.sellDate} @ {p.sellPrice?.toFixed(2)}
                          {' | '}{p.shares}股
                        </p>
                      </div>
                      <div className={`position-pnl ${ret >= 0 ? 'positive' : 'negative'}`}>
                        {ret >= 0 ? '+' : ''}{(ret * 100).toFixed(2)}%
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* ══════════ PnL Tab ══════════ */}
        {tab === 'pnl' && (
          <div className="detail-stack">
            {pnlLoading && <div className="state-card">计算收益中...</div>}
            {pnl && !pnlLoading && (
              <>
                <div className="card">
                  <div className="section-title"><h3>收益摘要</h3></div>
                  <div className="stat-grid">
                    <div className="stat-box">
                      <span>总盈亏</span>
                      <strong className={pnl.totalPnl >= 0 ? 'positive' : 'negative'}>
                        {pnl.totalPnl >= 0 ? '+' : ''}{pnl.totalPnl.toFixed(2)}
                      </strong>
                    </div>
                    <div className="stat-box">
                      <span>总收益率</span>
                      <strong className={pnl.totalPnlPercent >= 0 ? 'positive' : 'negative'}>
                        {(pnl.totalPnlPercent * 100).toFixed(2)}%
                      </strong>
                    </div>
                    <div className="stat-box">
                      <span>胜率</span>
                      <strong>{(pnl.winRate * 100).toFixed(1)}%</strong>
                    </div>
                    <div className="stat-box">
                      <span>平均收益</span>
                      <strong>{(pnl.avgPnlPercent * 100).toFixed(2)}%</strong>
                    </div>
                    <div className="stat-box">
                      <span>最大回撤</span>
                      <strong>{(pnl.maxDrawdown * 100).toFixed(2)}%</strong>
                    </div>
                    <div className="stat-box">
                      <span>在持 / 已平</span>
                      <strong>{pnl.openCount} / {pnl.closedCount}</strong>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="section-title"><h3>逐笔明细</h3></div>
                  {pnl.positions.length === 0 ? (
                    <p className="empty-hint">暂无持仓记录</p>
                  ) : (
                    pnl.positions.map((p) => (
                      <div className="position-row" key={p.id}>
                        <div className="position-info">
                          <strong>{p.symbol}</strong>
                          <p className="position-meta">
                            {p.buyDate} @ {p.buyPrice.toFixed(2)}
                            {' → '}
                            {p.status === 'closed'
                              ? `${p.sellDate} @ ${p.sellPrice?.toFixed(2)}`
                              : `当前 ${p.currentPrice?.toFixed(2) ?? '--'}`
                            }
                            {' | '}{p.shares}股 | {p.holdingDays}天
                          </p>
                        </div>
                        <div className={`position-pnl ${p.pnl >= 0 ? 'positive' : 'negative'}`}>
                          {p.pnl >= 0 ? '+' : ''}{p.pnl.toFixed(2)}
                          <span className="position-pnl-sub">
                            {(p.pnlPercent * 100).toFixed(2)}% | {p.status === 'open' ? '在持' : '已平'}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}
            {!pnl && !pnlLoading && (
              <div className="state-card">点击「收益」标签加载数据</div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function formatMoney(value: number) {
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

export default BasketDetail;
