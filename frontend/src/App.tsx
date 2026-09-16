import { useState } from 'react';

type Snapshot = { symbol: string; price: number | null; timestamp: string; source: string; status: string };
type Research = { bias: string; score: number; confidence: number; regime: string; explanation: string[]; invalidation: string; alternative_scenario: string; snapshot: Snapshot };
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const DISCLAIMER = 'This tool provides market research and analysis assistance only. It is not financial advice, a recommendation to buy or sell, or a substitute for professional advice.';

export default function App() {
  const [symbol, setSymbol] = useState('AAPL');
  const [assetClass, setAssetClass] = useState('stock');
  const [result, setResult] = useState<Research | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  async function analyze() {
    setLoading(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/research/analyze?symbol=${encodeURIComponent(symbol)}&asset_class=${assetClass}&timeframe=1day`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || 'Research request failed');
      setResult(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); setResult(null); }
    finally { setLoading(false); }
  }
  return <main className="shell">
    <header><div><span className="eyebrow">PROFITFORGE</span><h1>Adaptive Market Research</h1><p>Evidence-first market analysis for stocks, forex and crypto.</p></div><div className="status">● Research mode</div></header>
    <section className="controls"><input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} aria-label="Symbol"/><select value={assetClass} onChange={e => setAssetClass(e.target.value)}><option value="stock">Stock</option><option value="crypto">Crypto</option><option value="forex">Forex</option></select><button onClick={analyze} disabled={loading}>{loading ? 'Analyzing…' : 'Analyze'}</button></section>
    {error && <div className="error">{error}</div>}
    {!result && !loading && <section className="empty"><h2>Research workspace</h2><p>Enter an instrument and run analysis. Live data is fetched by the backend and validated before analysis.</p></section>}
    {result && <section className="grid">
      <article className="hero card"><div><span className="label">Current price</span><div className="price">{result.snapshot.price?.toLocaleString() ?? 'Unavailable'}</div><small>{result.snapshot.status} · {result.snapshot.source} · {new Date(result.snapshot.timestamp).toLocaleString()}</small></div><div className="score"><span>Score</span><strong>{result.score}</strong><small>{result.bias}</small></div></article>
      <article className="card"><span className="label">Confidence</span><strong className="metric">{result.confidence}%</strong><p>Regime: <b>{result.regime}</b></p></article>
      <article className="card"><span className="label">Why this matters</span><ul>{result.explanation.map((x, i) => <li key={i}>{x}</li>)}</ul></article>
      <article className="card"><span className="label">Risk framing</span><p><b>Invalidation:</b> {result.invalidation}</p><p><b>Alternative:</b> {result.alternative_scenario}</p></article>
    </section>}
    <footer>{DISCLAIMER} Trading and investing involve substantial risk of loss.</footer>
  </main>;
}
