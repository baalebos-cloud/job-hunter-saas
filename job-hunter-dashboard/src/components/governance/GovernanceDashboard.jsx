import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Download, Moon, RefreshCw, ShieldCheck, Sun } from 'lucide-react';
import { apiErrorMessage, filenameFromDisposition } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const POLL_MS = 10000;
const auth = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

// Theme tokens scoped to this page; both themes meet WCAG AA contrast.
const THEME_CSS = `
.gov{--bg:#f6f7f9;--surface:#ffffff;--border:#e3e6eb;--text:#151a21;--muted:#5b6573;--accent:#0f766e;--accent-text:#ffffff;
--warn-bg:#fff7e6;--warn-border:#f2c46d;--warn-text:#7a4b00;--crit-bg:#fdecec;--crit-border:#ef9a9a;--crit-text:#8a1c1c;--bar:#0f766e;--bar-alt:#c2410c;}
.gov[data-theme=dark]{--bg:#0e1116;--surface:#161b22;--border:#2a313c;--text:#e6e9ee;--muted:#9aa4b2;--accent:#2dd4bf;--accent-text:#04201d;
--warn-bg:#2b2110;--warn-border:#8a6418;--warn-text:#f5c86a;--crit-bg:#2d1416;--crit-border:#8f3439;--crit-text:#ffb4b4;--bar:#2dd4bf;--bar-alt:#fb923c;}
.gov{background:var(--bg);color:var(--text)}
.gov .card{background:var(--surface);border:1px solid var(--border);border-radius:14px}
.gov .muted{color:var(--muted)}
.gov .btn{border:1px solid var(--border);border-radius:10px;padding:.5rem .9rem;font-size:.875rem;background:var(--surface);color:var(--text)}
.gov .btn-primary{background:var(--accent);color:var(--accent-text);border-color:var(--accent)}
.gov .tab[aria-selected=true]{border-bottom:2px solid var(--accent);color:var(--text)}
.gov table{width:100%;border-collapse:collapse;font-size:.8125rem}
.gov th,.gov td{padding:.5rem .6rem;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
.gov select,.gov input{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:.4rem .6rem}
`;

function initialTheme() {
  try {
    const saved = localStorage.getItem('gov-theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* storage unavailable */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

const fmtMs = v => (v == null ? '—' : `${Math.round(v)} ms`);

function Stat({ label, value, tone }) {
  return (
    <div className="card p-4">
      <p className="text-xs muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-semibold mt-1" style={tone ? { color: tone } : undefined}>{value}</p>
    </div>
  );
}

function Bars({ series, field, color, label }) {
  const max = Math.max(1, ...series.map(s => s[field] || 0));
  return (
    <figure className="card p-4">
      <figcaption className="text-sm font-medium mb-3">{label}</figcaption>
      <div className="flex items-end gap-1 h-28" role="img" aria-label={`${label}: ${series.map(s => s[field] || 0).join(', ')}`}>
        {series.map(s => (
          <div key={s.minute} className="flex-1 rounded-t" title={`${new Date(s.minute * 1000).toLocaleTimeString()}: ${s[field] ?? 0}`}
               style={{ height: `${Math.max(2, ((s[field] || 0) / max) * 100)}%`, background: color }} />
        ))}
      </div>
    </figure>
  );
}

function Overview({ summary, error, lastUpdated }) {
  if (error) return <p role="alert" className="card p-4">{error}</p>;
  if (!summary) return <p role="status" className="muted">Loading live metrics…</p>;
  const denied = summary.unauthorized_401 + summary.forbidden_403;
  return (
    <div className="space-y-4">
      <div aria-live="polite" className="space-y-2">
        {summary.alerts.length === 0 && <p className="card p-3 text-sm flex items-center gap-2"><ShieldCheck size={16} aria-hidden="true" />No active alerts.</p>}
        {summary.alerts.map(a => (
          <div key={a.kind} role="alert" className="rounded-xl p-3 text-sm flex gap-2 items-start"
               style={{ background: `var(--${a.severity === 'critical' ? 'crit' : 'warn'}-bg)`, border: `1px solid var(--${a.severity === 'critical' ? 'crit' : 'warn'}-border)`, color: `var(--${a.severity === 'critical' ? 'crit' : 'warn'}-text)` }}>
            <AlertTriangle size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
            <span><strong className="uppercase text-xs mr-2">{a.severity}</strong>{a.message}</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label={`Requests (${summary.window_minutes} min)`} value={summary.requests} />
        <Stat label="p95 latency" value={fmtMs(summary.p95_ms)} tone={summary.p95_ms > summary.thresholds.p95_ms ? 'var(--bar-alt)' : undefined} />
        <Stat label="401 / 403" value={`${summary.unauthorized_401} / ${summary.forbidden_403}`} tone={denied >= summary.thresholds.unauthorized ? 'var(--crit-text)' : undefined} />
        <Stat label="Server errors" value={summary.server_errors} />
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        <Bars series={summary.series} field="total" color="var(--bar)" label="Requests per minute" />
        <Bars series={summary.series.map(s => ({ ...s, denied: s.s401 + s.s403 }))} field="denied" color="var(--bar-alt)" label="Unauthorized / forbidden per minute" />
      </div>
      <p className="text-xs muted">Fleet-wide window across all API replicas. Thresholds: p95 {summary.thresholds.p95_ms} ms, {summary.thresholds.unauthorized} denied requests per window. Updated {lastUpdated?.toLocaleTimeString()}.</p>
    </div>
  );
}

function AuditTrail() {
  const [rows, setRows] = useState([]);
  const [outcome, setOutcome] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(async (append = false) => {
    setError('');
    try {
      const before = append && rows.length ? rows[rows.length - 1].id : undefined;
      const res = await axios.get(`${API}/governance/audit`, { headers: auth(), params: { outcome: outcome || undefined, limit: 100, before_id: before } });
      setRows(prev => (append ? [...prev, ...res.data] : res.data));
    } catch (err) { setError(await apiErrorMessage(err, 'The audit trail could not be loaded.')); }
  }, [outcome, rows]);
  useEffect(() => { load(false); }, [outcome]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <section className="space-y-3">
      <div className="flex gap-3 items-center flex-wrap">
        <label className="text-sm">Outcome{' '}
          <select value={outcome} onChange={e => setOutcome(e.target.value)} className="ml-2">
            <option value="">All</option><option value="denied">Denied (401/403)</option>
            <option value="error">Server error</option><option value="client_error">Client error</option><option value="success">Success</option>
          </select>
        </label>
        <button className="btn" onClick={() => load(false)}><RefreshCw size={14} className="inline mr-1" aria-hidden="true" />Refresh</button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="card overflow-x-auto">
        <table>
          <thead><tr><th>Time (UTC)</th><th>Actor</th><th>Role</th><th>Request / event</th><th>Status</th><th>Latency</th><th>IP (masked)</th><th>Trace</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td className="whitespace-nowrap">{r.ts.replace('T', ' ').slice(0, 19)}</td>
                <td>{r.actor || '—'}</td><td>{r.actor_role || '—'}</td>
                <td>{r.kind === 'event' ? <strong>{r.action}</strong> : <code>{r.method} {r.route}</code>}</td>
                <td>{r.status ?? '—'}</td><td>{fmtMs(r.latency_ms)}</td><td>{r.ip || '—'}</td>
                <td><code className="text-xs">{r.trace_id.slice(0, 12)}</code></td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={8} className="muted">No records.</td></tr>}
          </tbody>
        </table>
      </div>
      {rows.length >= 100 && <button className="btn" onClick={() => load(true)}>Load older records</button>}
    </section>
  );
}

function AccessControl({ canManage }) {
  const [matrix, setMatrix] = useState(null);
  const [holders, setHolders] = useState([]);
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState(null);
  const load = useCallback(async () => {
    try {
      const [m, u] = await Promise.all([
        axios.get(`${API}/rbac/matrix`, { headers: auth() }),
        axios.get(`${API}/rbac/users`, { headers: auth(), params: { q: query || undefined } }),
      ]);
      setMatrix(m.data); setHolders(u.data);
    } catch (err) { setMessage({ ok: false, text: await apiErrorMessage(err, 'Roles could not be loaded.') }); }
  }, [query]);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const assign = async (user, role) => {
    setMessage(null);
    try {
      await axios.put(`${API}/rbac/users/${user.id}/role`, { role: role || null }, { headers: auth() });
      setMessage({ ok: true, text: `${user.email} is now ${role || 'without a governance role'}. Their existing sessions were signed out.` });
      load();
    } catch (err) { setMessage({ ok: false, text: await apiErrorMessage(err, 'The role could not be changed.') }); }
  };
  if (!matrix) return <p role="status" className="muted">{message?.text || 'Loading roles…'}</p>;
  const roles = Object.keys(matrix.roles);
  const permissions = Object.keys(matrix.permissions);
  return (
    <section className="space-y-4">
      {message && <p role={message.ok ? 'status' : 'alert'} className="card p-3 text-sm">{message.text}</p>}
      <div className="card p-4 space-y-3">
        <form className="flex gap-2 flex-wrap" onSubmit={e => { e.preventDefault(); load(); }}>
          <label htmlFor="rbac-search" className="sr-only">Search users by email</label>
          <input id="rbac-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by email to grant a role" className="flex-1 min-w-[14rem]" />
          <button className="btn">Search</button>
        </form>
        <table>
          <thead><tr><th>User</th><th>Verified</th><th>Governance role</th></tr></thead>
          <tbody>
            {holders.map(u => (
              <tr key={u.id}>
                <td>{u.email}<span className="block muted text-xs">{u.full_name}</span></td>
                <td>{u.is_verified ? 'Yes' : 'No'}</td>
                <td>{canManage ? (
                  <select aria-label={`Role for ${u.email}`} value={u.role || ''} onChange={e => assign(u, e.target.value)}>
                    <option value="">None</option>{roles.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>) : (u.role || '—')}</td>
              </tr>
            ))}
            {!holders.length && <tr><td colSpan={3} className="muted">No matching users.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="card overflow-x-auto">
        <table>
          <caption className="text-left p-3 font-medium">Policy matrix</caption>
          <thead><tr><th>Permission</th>{roles.map(r => <th key={r}>{r}</th>)}</tr></thead>
          <tbody>
            {permissions.map(p => (
              <tr key={p}>
                <td><code>{p}</code><span className="block muted text-xs">{matrix.permissions[p]}</span></td>
                {roles.map(r => <td key={r} aria-label={`${r} ${matrix.roles[r].permissions.includes(p) ? 'has' : 'lacks'} ${p}`}>{matrix.roles[r].permissions.includes(p) ? '●' : ''}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Reports() {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const download = async format => {
    setBusy(format); setError('');
    try {
      const res = await axios.get(`${API}/governance/reports/weekly`, { headers: auth(), params: { format }, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = filenameFromDisposition(res.headers['content-disposition'], `weekly-report.${format}`);
      document.body.appendChild(link); link.click(); link.remove();
      URL.revokeObjectURL(url);
    } catch (err) { setError(await apiErrorMessage(err, 'The report could not be generated.')); } finally { setBusy(''); }
  };
  return (
    <section className="card p-5 space-y-3">
      <h2 className="font-semibold">Weekly analytical report</h2>
      <p className="text-sm muted">Last 7 days: request volume, p50/p95/p99 latency, denied requests by route, server errors and governance events (role changes, data exports, erasures, retention runs).</p>
      <div className="flex gap-2 flex-wrap">
        {[['md', 'Markdown'], ['csv', 'CSV'], ['json', 'JSON']].map(([format, label]) => (
          <button key={format} className="btn btn-primary" disabled={!!busy} onClick={() => download(format)}>
            <Download size={14} className="inline mr-1" aria-hidden="true" />{busy === format ? 'Preparing…' : label}
          </button>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export default function GovernanceDashboard({ permissions = [] }) {
  const [theme, setTheme] = useState(initialTheme);
  const tabs = useMemo(() => [
    ['overview', 'Live monitoring', permissions.includes('metrics:read')],
    ['audit', 'Audit trail', permissions.includes('audit:read')],
    ['access', 'Access control', permissions.includes('users:read')],
    ['reports', 'Reports', permissions.includes('reports:read')],
  ].filter(t => t[2]), [permissions]);
  const [tab, setTab] = useState(tabs[0]?.[0]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => { try { localStorage.setItem('gov-theme', theme); } catch { /* ignore */ } }, [theme]);
  useEffect(() => {
    if (!permissions.includes('metrics:read')) return undefined;
    let active = true;
    const poll = async () => {
      try {
        const res = await axios.get(`${API}/governance/summary`, { headers: auth() });
        if (active) { setSummary(res.data); setError(''); setLastUpdated(new Date()); }
      } catch (err) { if (active) setError(await apiErrorMessage(err, 'Live metrics are unavailable.')); }
    };
    poll();
    const timer = setInterval(() => { if (!document.hidden) poll(); }, POLL_MS);
    return () => { active = false; clearInterval(timer); };
  }, [permissions]);

  if (!tabs.length) return <p role="alert">Your role does not include governance permissions.</p>;
  return (
    <div className="gov rounded-2xl p-4 md:p-6 -m-2" data-theme={theme}>
      <style>{THEME_CSS}</style>
      <header className="flex flex-wrap gap-3 items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold">Security &amp; governance</h1>
          <p className="text-sm muted">Monitoring, audit evidence and access control for SOC 2 and GDPR.</p>
        </div>
        <button className="btn" onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
          {theme === 'dark' ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
        </button>
      </header>
      {summary?.alerts?.length > 0 && tab !== 'overview' && (
        <p role="alert" className="rounded-xl p-2 text-sm mb-3" style={{ background: 'var(--crit-bg)', color: 'var(--crit-text)', border: '1px solid var(--crit-border)' }}>
          {summary.alerts.length} active alert{summary.alerts.length > 1 ? 's' : ''}: {summary.alerts.map(a => a.message).join(' · ')}
        </p>
      )}
      <div role="tablist" aria-label="Governance sections" className="flex gap-4 border-b mb-4 overflow-x-auto" style={{ borderColor: 'var(--border)' }}>
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" id={`gov-tab-${id}`} aria-controls={`gov-panel-${id}`} aria-selected={tab === id}
                  className="tab py-2 text-sm muted whitespace-nowrap" onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      <div role="tabpanel" id={`gov-panel-${tab}`} aria-labelledby={`gov-tab-${tab}`}>
        {tab === 'overview' && <Overview summary={summary} error={error} lastUpdated={lastUpdated} />}
        {tab === 'audit' && <AuditTrail />}
        {tab === 'access' && <AccessControl canManage={permissions.includes('users:manage_roles')} />}
        {tab === 'reports' && <Reports />}
      </div>
    </div>
  );
}
