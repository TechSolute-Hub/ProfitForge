import { useEffect, useState } from 'react';

import { useAuth } from './auth/AuthContext';

type Snapshot = {
  symbol: string;
  price: number | null;
  timestamp: string;
  source: string;
  status: string;
};
type Timeframe = {
  timeframe: string;
  score: number;
  bias: string;
  confidence: number;
  regime: string;
  factors: Record<string, number>;
  contributions: Record<string, number>;
  indicators: Record<string, number>;
  structure: Record<string, unknown>;
  data_quality: string;
  unavailable_factors: string[];
};
type Research = {
  symbol: string;
  asset_class: 'stock' | 'crypto' | 'forex';
  timeframe: string;
  bias: string;
  score: number;
  confidence: number;
  regime: string;
  explanation: string[];
  invalidation: string;
  alternative_scenario: string;
  snapshot: Snapshot;
  mtf_score: number;
  mtf_alignment: number;
  data_quality: string;
  factors: Record<string, number>;
  factor_contributions: Record<string, number>;
  indicators: Record<string, number>;
  structure: Record<string, unknown>;
  timeframe_analysis: Record<string, Timeframe>;
};
type SavedAnalysis = {
  id: string;
  name: string;
  symbol: string;
  asset_class: string;
  timeframe: string;
  created_at: string;
};
type Watchlist = {
  id: string;
  name: string;
  watchlist_items?: Array<{ id: string; symbol: string; asset_class: string }>;
};

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const DISCLAIMER = 'This tool provides market research and analysis assistance only. It is **not** financial advice, a recommendation to buy or sell, or a substitute for professional advice. Trading and investing involve substantial risk of loss. Past performance is not indicative of future results. Users are solely responsible for their own decisions.';

function AuthPanel() {
  const { configured, loading, user, signIn, signUp, signInWithGoogle, signOut } = useAuth();
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  if (loading) return <div className="auth-card"><span className="label">Account</span><p>Restoring session…</p></div>;
  if (!configured) return <div className="auth-card"><span className="label">Account</span><p>Authentication is not configured in this deployment. Research remains available.</p></div>;
  if (user) {
    return <div className="auth-card auth-signed-in"><div><span className="label">Authenticated</span><strong>{user.email || 'Signed-in user'}</strong></div><button className="secondary" onClick={() => void signOut()}>Sign out</button></div>;
  }

  async function submit() {
    setBusy(true); setMessage('');
    try {
      if (mode === 'sign-in') {
        await signIn(email, password);
        setMessage('Signed in.');
      } else {
        const confirmationRequired = await signUp(email, password);
        setMessage(confirmationRequired ? 'Account created. Check your email to confirm it, then sign in.' : 'Account created and signed in.');
        if (confirmationRequired) setMode('sign-in');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Authentication failed');
    } finally { setBusy(false); }
  }

  return <div className="auth-card">
    <div className="auth-heading"><div><span className="label">Account</span><strong>{mode === 'sign-in' ? 'Sign in to save research' : 'Create your account'}</strong></div><button className="link-button" onClick={() => setMode(mode === 'sign-in' ? 'sign-up' : 'sign-in')}>{mode === 'sign-in' ? 'Create account' : 'Sign in'}</button></div>
    <div className="auth-fields"><input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} /><input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} /><button onClick={() => void submit()} disabled={busy || !email || password.length < 6}>{busy ? 'Working…' : mode === 'sign-in' ? 'Sign in' : 'Create account'}</button><button className="secondary" onClick={() => void signInWithGoogle()} disabled={busy}>Continue with Google</button></div>
    {message && <p className="auth-message">{message}</p>}
  </div>;
}

async function userStateRequest(path: string, token: string, options: RequestInit = {}) {
  const response = await fetch(`${API}/api/v1/user-state${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...(options.headers || {}) },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || 'User-state request failed');
  }
  if (response.status === 204) return null;
  return response.json();
}

export default function App() {
  const { user, session } = useAuth();
  const [symbol, setSymbol] = useState('AAPL');
  const [assetClass, setAssetClass] = useState('stock');
  const [timeframe, setTimeframe] = useState('1day');
  const [result, setResult] = useState<Research | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [savedMessage, setSavedMessage] = useState('');
  const [savedAnalyses, setSavedAnalyses] = useState<SavedAnalysis[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);

  async function refreshUserState() {
    if (!session?.access_token) { setSavedAnalyses([]); setWatchlists([]); return; }
    try {
      const [saved, lists] = await Promise.all([
        userStateRequest('/saved-analyses', session.access_token),
        userStateRequest('/watchlists', session.access_token),
      ]);
      setSavedAnalyses(saved || []);
      setWatchlists(lists || []);
    } catch (e) {
      setSavedMessage(e instanceof Error ? e.message : 'Could not load saved state');
    }
  }

  useEffect(() => { void refreshUserState(); }, [session?.access_token]);

  async function analyze() {
    setLoading(true); setError(''); setSavedMessage('');
    try {
      const response = await fetch(`${API}/api/v1/research/analyze?symbol=${encodeURIComponent(symbol)}&asset_class=${assetClass}&timeframe=${timeframe}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || 'Research request failed');
      setResult(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); setResult(null); }
    finally { setLoading(false); }
  }

  async function saveCurrentAnalysis() {
    if (!result || !session?.access_token) return;
    setSavedMessage('Saving…');
    try {
      await userStateRequest('/saved-analyses', session.access_token, { method: 'POST', body: JSON.stringify({ name: `${result.symbol} ${result.timeframe} research`, result }) });
      await userStateRequest('/history', session.access_token, { method: 'POST', body: JSON.stringify(result) });
      await refreshUserState();
      setSavedMessage('Analysis saved to your research history.');
    } catch (e) { setSavedMessage(e instanceof Error ? e.message : 'Could not save analysis'); }
  }

  async function addToWatchlist() {
    if (!result || !session?.access_token) return;
    setSavedMessage('Updating watchlist…');
    try {
      await userStateRequest('/watchlists/items', session.access_token, { method: 'POST', body: JSON.stringify({ symbol: result.symbol, asset_class: result.asset_class }) });
      await refreshUserState();
      setSavedMessage(`${result.symbol} added to your default watchlist.`);
    } catch (e) { setSavedMessage(e instanceof Error ? e.message : 'Could not update watchlist'); }
  }

  return <main className="shell">
    <header><div><span className="eyebrow">PROFITFORGE</span><h1>Adaptive Market Research</h1><p>Evidence-first multi-timeframe analysis for stocks, forex and crypto.</p></div><div className="status">● Research mode</div></header>
    <AuthPanel />
    <section className="controls">
      <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} aria-label="Symbol" />
      <select value={assetClass} onChange={e => setAssetClass(e.target.value)}><option value="stock">Stock</option><option value="crypto">Crypto</option><option value="forex">Forex</option></select>
      <select value={timeframe} onChange={e => setTimeframe(e.target.value)} aria-label="Primary timeframe"><option value="1h">1H</option><option value="4h">4H</option><option value="1day">Daily</option><option value="1week">Weekly</option></select>
      <button onClick={() => void analyze()} disabled={loading}>{loading ? 'Analyzing…' : 'Analyze'}</button>
    </section>
    {error && <div className="error">{error}</div>}
    {savedMessage && <div className="notice">{savedMessage}</div>}
    {!result && !loading && <section className="empty"><h2>Research workspace</h2><p>Live data is fetched and validated by the backend. Phase 2 combines technical factors, confirmed structure, regime detection and multi-timeframe confluence.</p></section>}
    {result && <section className="grid">
      <article className="hero card"><div><span className="label">Current price</span><div className="price">{result.snapshot.price?.toLocaleString() ?? 'Unavailable'}</div><small>{result.snapshot.status} · {result.snapshot.source} · {new Date(result.snapshot.timestamp).toLocaleString()}</small></div><div className="score"><span>Score</span><strong>{result.score}</strong><small>{result.bias}</small></div></article>
      <article className="card"><span className="label">Intelligence</span><strong className="metric">{result.confidence}%</strong><p>Confidence · <b>{result.regime}</b></p><p>Data quality · <b>{result.data_quality}</b></p><p>MTF alignment · <b>{result.mtf_alignment}%</b></p></article>
      <article className="card wide action-card"><span className="label">User research state</span>{user ? <div className="action-row"><button onClick={() => void saveCurrentAnalysis()}>Save analysis</button><button className="secondary" onClick={() => void addToWatchlist()}>Add to watchlist</button></div> : <p>Sign in above to save this analysis and maintain a private watchlist.</p>}</article>
      <article className="card wide"><span className="label">Multi-timeframe confluence</span><div className="tf-grid">{Object.values(result.timeframe_analysis).map(tf => <div className="tf" key={tf.timeframe}><b>{tf.timeframe}</b><strong>{tf.score}</strong><span>{tf.bias}</span><small>{tf.regime}</small></div>)}</div></article>
      <article className="card"><span className="label">Factor scores</span>{Object.entries(result.factors).map(([name, value]) => <div className="factor" key={name}><span>{name.replaceAll('_', ' ')}</span><b>{value.toFixed(0)}</b></div>)}</article>
      <article className="card"><span className="label">Technical snapshot</span><p>RSI(14): <b>{result.indicators.rsi14?.toFixed(1)}</b></p><p>ADX(14): <b>{result.indicators.adx14?.toFixed(1)}</b></p><p>MACD histogram: <b>{result.indicators.macd_histogram?.toFixed(4)}</b></p><p>ATR: <b>{result.indicators.atr14?.toFixed(4)}</b></p></article>
      <article className="card"><span className="label">Why this matters</span><ul>{result.explanation.map((x, i) => <li key={i}>{x}</li>)}</ul></article>
      <article className="card"><span className="label">Risk framing</span><p><b>Invalidation:</b> {result.invalidation}</p><p><b>Alternative:</b> {result.alternative_scenario}</p></article>
      {user && <article className="card wide"><span className="label">Your saved research</span><div className="saved-grid">{savedAnalyses.length ? savedAnalyses.slice(0, 8).map(item => <div className="saved-item" key={item.id}><strong>{item.name}</strong><small>{item.symbol} · {item.timeframe} · {new Date(item.created_at).toLocaleDateString()}</small></div>) : <p>No saved analyses yet.</p>}</div><div className="watchlist-summary"><span className="label">Default watchlist</span>{watchlists.flatMap(list => list.watchlist_items || []).length ? watchlists.flatMap(list => list.watchlist_items || []).map(item => <span className="chip" key={item.id}>{item.symbol} · {item.asset_class}</span>) : <small>No symbols saved yet.</small>}</div></article>}
    </section>}
    <footer>{DISCLAIMER}</footer>
  </main>;
}
