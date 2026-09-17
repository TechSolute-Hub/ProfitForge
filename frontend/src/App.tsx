import { useState } from 'react';

type Snapshot = { symbol: string; price: number | null; timestamp: string; source: string; status: string };
type Timeframe = { timeframe: string; score: number; bias: string; confidence: number; regime: string; factors: Record<string, number>; contributions: Record<string, number>; indicators: Record<string, number>; structure: Record<string, unknown>; data_quality: string; unavailable_factors: string[] };
type Research = { bias: string; score: number; confidence: number; regime: string; explanation: string[]; invalidation: string; alternative_scenario: string; snapshot: Snapshot; mtf_score: number; mtf_alignment: number; data_quality: string; factors: Record<string, number>; factor_contributions: Record<string, number>; indicators: Record<string, number>; structure: Record<string, unknown>; timeframe_analysis: Record<string, Timeframe> };

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const DISCLAIMER = 'This tool provides market research and analysis assistance only. It is **not** financial advice, a recommendation to buy or sell, or a substitute for professional advice. Trading and investing involve substantial risk of loss. Past performance is not indicative of future results. Users are solely responsible for their own decisions.';

export default function App() {
  const [symbol, setSymbol] = useState('AAPL');
  const [assetClass, setAssetClass] = useState('stock');
  const [timeframe, setTimeframe] = useState('1day');
  const [result, setResult] = useState<Research | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function analyze() {
    setLoading(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/research/analyze?symbol=${encodeURIComponent(symbol)}&asset_class=${assetClass}&timeframe=${timeframe}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || 'Research request failed');
      setResult(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); setResult(null); }
    finally { setLoading(false); }
  }

  return <main className="shell">
    <header><div><span className="eyebrow">PROFITFORGE</span><h1>Adaptive Market Research</h1><p>Evidence-first multi-timeframe analysis for stocks, forex and crypto.</p></div><div className="status">● Research mode</div></header>
    <section className="controls">
      <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} aria-label="Symbol"/>
      <select value={assetClass} onChange={e => setAssetClass(e.target.value)}><option value="stock">Stock</option><option value="crypto">Crypto</option><option value="forex">Forex</option></select>
      <select value={timeframe} onChange={e => setTimeframe(e.target.value)} aria-label="Primary timeframe"><option value="1h">1H</option><option value="4h">4H</option><option value="1day">Daily</option><option value="1week">Weekly</option></select>
      <button onClick={analyze} disabled={loading}>{loading ? 'Analyzing…' : 'Analyze'}</button>
    </section>
    {error && <div className="error">{error}</div>}
    {!result && !loading && <section className="empty"><h2>Research workspace</h2><p>Live data is fetched and validated by the backend. Phase 2 combines technical factors, confirmed structure, regime detection and multi-timeframe confluence.</p></section>}
    {result && <section className="grid">
      <article className="hero card"><div><span className="label">Current price</span><div className="price">{result.snapshot.price?.toLocaleString() ?? 'Unavailable'}</div><small>{result.snapshot.status} · {result.snapshot.source} · {new Date(result.snapshot.timestamp).toLocaleString()}</small></div><div className="score"><span>Score</span><strong>{result.score}</strong><small>{result.bias}</small></div></article>
      <article className="card"><span className="label">Intelligence</span><strong className="metric">{result.confidence}%</strong><p>Confidence · <b>{result.regime}</b></p><p>Data quality · <b>{result.data_quality}</b></p><p>MTF alignment · <b>{result.mtf_alignment}%</b></p></article>
      <article className="card wide"><span className="label">Multi-timeframe confluence</span><div className="tf-grid">{Object.values(result.timeframe_analysis).map(tf => <div className="tf" key={tf.timeframe}><b>{tf.timeframe}</b><strong>{tf.score}</strong><span>{tf.bias}</span><small>{tf.regime}</small></div>)}</div></article>
      <article className="card"><span className="label">Factor scores</span>{Object.entries(result.factors).map(([name, value]) => <div className="factor" key={name}><span>{name.replaceAll('_', ' ')}</span><b>{value.toFixed(0)}</b></div>)}</article>
      <article className="card"><span className="label">Technical snapshot</span><p>RSI(14): <b>{result.indicators.rsi14?.toFixed(1)}</b></p><p>ADX(14): <b>{result.indicators.adx14?.toFixed(1)}</b></p><p>MACD histogram: <b>{result.indicators.macd_histogram?.toFixed(4)}</b></p><p>ATR: <b>{result.indicators.atr14?.toFixed(4)}</b></p></article>
      <article className="card"><span className="label">Why this matters</span><ul>{result.explanation.map((x, i) => <li key={i}>{x}</li>)}</ul></article>
      <article className="card"><span className="label">Risk framing</span><p><b>Invalidation:</b> {result.invalidation}</p><p><b>Alternative:</b> {result.alternative_scenario}</p></article>
    </section>}
    <footer>{DISCLAIMER}</footer>
  </main>;
}
