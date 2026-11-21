import { useState, useEffect } from 'react';
import axios from 'axios';
import { errorText } from '../../lib/session';

const GRAFANA_URL = import.meta.env.VITE_GRAFANA_URL || '';

// Short device description from a User-Agent string (display only).
function device(ua) {
  if (!ua) return '—';
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad|iOS/.test(ua) ? 'iOS'
    : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
  const browser = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Chrome\//.test(ua) ? 'Chrome'
    : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : /curl|python|httpx|bot|spider/i.test(ua) ? 'Script/bot' : '';
  return [browser, os].filter(Boolean).join(' · ') || ua.slice(0, 40);
}
const EVENT_TONE = {
  'login.success': 'bg-emerald-500/15 text-emerald-300', 'signup': 'bg-sky-500/15 text-sky-300',
  'hr.signup': 'bg-sky-500/15 text-sky-300', 'login.failed': 'bg-rose-500/15 text-rose-300',
  'login.blocked': 'bg-rose-500/25 text-rose-200', 'login.denied': 'bg-amber-500/15 text-amber-300',
};

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const h = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [apps, setApps] = useState([]);
  const [tab, setTab] = useState('stats');
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [msg, setMsg] = useState('');
  const [testingAI, setTestingAI] = useState(false);
  const [aiReport, setAIReport] = useState(null);
  const [aiError, setAIError] = useState('');
  const [automation, setAutomation] = useState(null);
  const [automationError, setAutomationError] = useState('');
  const [processing, setProcessing] = useState(false);
  const [pendingHR, setPendingHR] = useState(null);
  const [hrError, setHrError] = useState('');
  const [approving, setApproving] = useState(null);
  const [secSummary, setSecSummary] = useState(null);
  const [secEvents, setSecEvents] = useState([]);
  const [secNext, setSecNext] = useState(null);
  const [secFilter, setSecFilter] = useState({ event: '', q: '', ip: '' });
  const [secError, setSecError] = useState('');
  const [secLoading, setSecLoading] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('token')) { window.location.href = '/login'; return; }
    axios.get(`${API}/admin/stats`, { headers: h() })
      .then(r => setStats(r.data))
      .catch(e => { if (e.response?.status === 403) { alert('Admin access required'); window.location.href = '/'; } })
      .finally(() => setLoading(false));
    // Deep links such as /admin?tab=hr (used by the "new employer" alert email).
    const requested = new URLSearchParams(window.location.search).get('tab');
    if (requested === 'hr') load('hr');
  }, []);

  const load = async (t) => {
    setTab(t);
    if (t === 'users')   { const r = await axios.get(`${API}/admin/users`, { headers: h() }); setUsers(r.data); }
    if (t === 'jobs')    { const r = await axios.get(`${API}/admin/jobs`, { headers: h() }); setJobs(r.data); }
    if (t === 'apps')    { const r = await axios.get(`${API}/admin/applications`, { headers: h() }); setApps(r.data); }
    if (t === 'security') {
      setSecError('');
      try {
        const s = await axios.get(`${API}/admin/security/summary`, { headers: h() });
        setSecSummary(s.data);
        await loadSecurityEvents(secFilter);
      } catch (error) { setSecError(errorText(error, 'Could not load security data.')); }
    }
    if (t === 'hr') {
      setHrError('');
      try { const r = await axios.get(`${API}/hr-auth/pending`, { headers: h() }); setPendingHR(r.data); }
      catch (error) { setHrError(errorText(error, 'Could not load pending employer accounts.')); }
    }
    if (t === 'automation') {
      setAutomationError('');
      try { const r = await axios.get(`${API}/admin/automation`, { headers: h() }); setAutomation(r.data); }
      catch { setAutomationError('Could not load automation status.'); }
    }
  };

  const processNotifications = async () => {
    setProcessing(true); setAutomationError('');
    try {
      const { data } = await axios.post(`${API}/admin/automation/run`, {}, { headers: h(), timeout: 90000 });
      setMsg(`Notifications accepted: ${data.accepted}. Retrying: ${data.retrying}. Failed: ${data.failed}.`);
      await load('automation');
    } catch { setAutomationError('Could not complete notification processing. Check Railway and n8n executions.'); }
    finally { setProcessing(false); }
  };

  const testAI = async () => {
    setTestingAI(true); setAIReport(null); setAIError('');
    try {
      const { data } = await axios.post(`${API}/admin/resume-diagnostic`, {}, { headers: h(), timeout: 300000 });
      setAIReport(data);
    } catch (error) {
      setAIError(errorText(error, 'The diagnostic could not complete. Please try again.'));
    } finally { setTestingAI(false); }
  };

  const loadSecurityEvents = async (filter, beforeId = null) => {
    setSecLoading(true); setSecError('');
    try {
      const params = { limit: 100, ...Object.fromEntries(Object.entries(filter).filter(([, v]) => v)) };
      if (beforeId) params.before_id = beforeId;
      const { data } = await axios.get(`${API}/admin/security/events`, { headers: h(), params });
      setSecEvents(prev => (beforeId ? [...prev, ...data.events] : data.events));
      setSecNext(data.next_before_id);
    } catch (error) { setSecError(errorText(error, 'Could not load security events.')); }
    finally { setSecLoading(false); }
  };
  const applySecFilter = (next) => { const f = { ...secFilter, ...next }; setSecFilter(f); loadSecurityEvents(f); };

  const approveHR = async (account) => {
    if (!confirm(`Approve ${account.company_name || account.email} as an employer? They will be able to post jobs.`)) return;
    setApproving(account.id); setHrError('');
    try {
      const { data } = await axios.post(`${API}/hr-auth/approve/${account.id}`, {}, { headers: h() });
      setMsg(data.message || 'Employer account approved.');
      await load('hr');
    } catch (error) {
      setHrError(errorText(error, 'Could not approve this account. Please try again.'));
    } finally { setApproving(null); }
  };

  const makeHR = async (id) => {
    await axios.patch(`${API}/admin/users/${id}/make-hr`, {}, { headers: h() });
    setMsg('User promoted to HR'); load('users');
  };

  const delUser = async (id) => {
    if (!confirm('Delete user?')) return;
    await axios.delete(`${API}/admin/users/${id}`, { headers: h() }); load('users');
  };

  const delJob = async (id) => {
    if (!confirm('Delete job?')) return;
    await axios.delete(`${API}/admin/jobs/${id}`, { headers: h() }); load('jobs');
  };

  const scrape = async () => {
    setScraping(true);
    try {
      const r = await axios.post(`${API}/admin/scrape`, {}, { headers: h() });
      setMsg(`Scrape ${r.data.status || 'completed'}: ${r.data.total_saved} new jobs. See Automation for source results.`);
      const s = await axios.get(`${API}/admin/stats`, { headers: h() }); setStats(s.data);
    } catch { setMsg('❌ Scrape failed'); } finally { setScraping(false); }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  );

  const TABS = [
    { id: 'stats', label: '📊 Stats' },
    { id: 'ai', label: 'AI Resume Test' },
    { id: 'automation', label: 'Automation' },
    { id: 'hr', label: `🏢 HR Approvals${pendingHR?.length ? ` (${pendingHR.length})` : ''}` },
    { id: 'security', label: `🛡️ Security${secSummary?.suspicious_ips?.length ? ` (${secSummary.suspicious_ips.length} ⚠)` : ''}` },
    { id: 'users', label: '👥 Users' },
    { id: 'jobs',  label: '💼 Jobs' },
    { id: 'apps',  label: '📋 Applications' },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Navbar */}
      <div className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/" className="text-slate-400 hover:text-white text-sm font-bold">← Home</a>
          <span className="text-slate-700">|</span>
          <h1 className="text-base font-black">Admin Dashboard</h1>
          <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/20 uppercase tracking-widest">Admin</span>
        </div>
        <button onClick={scrape} disabled={scraping}
          className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-black transition-all disabled:bg-slate-700 disabled:cursor-not-allowed">
          {scraping ? '⏳ Scraping...' : '🔄 Run Scraper'}
        </button>
      </div>

      {msg && (
        <div className="mx-6 mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm font-bold flex justify-between">
          {msg} <button onClick={() => setMsg('')} className="text-slate-500 hover:text-white ml-4">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="px-6 mt-6 flex gap-1 border-b border-slate-800">
        {TABS.map(t => (
          <button key={t.id} onClick={() => load(t.id)}
            className={`px-5 py-2.5 text-sm font-black rounded-t-xl transition-all ${
              tab === t.id ? 'bg-slate-800 text-white border-b-2 border-emerald-500' : 'text-slate-500 hover:text-white'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-6">

        {tab === 'security' && (
          <section className="space-y-6 max-w-7xl">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <p className="text-slate-400 text-sm max-w-3xl">
                Sign-ins, sign-ups, password resets and admin actions with the full IP address and approximate location.
                Visible to admins only; every view is recorded. Entries are deleted after {secSummary?.retention_days ?? 90} days
                and when a user erases their account.
              </p>
              {GRAFANA_URL && (
                <a href={GRAFANA_URL} target="_blank" rel="noopener noreferrer"
                  className="text-xs font-black px-3 py-2 rounded-xl bg-orange-500/15 text-orange-300 hover:bg-orange-500/25">Open Grafana ↗</a>
              )}
            </div>
            {secError && <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm font-bold">{secError}</div>}
            {secSummary && !secSummary.geolocation_enabled && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-300 text-sm">
                Location lookup is off. Set <code className="font-mono">MAXMIND_LICENSE_KEY</code> on the backend (free GeoLite2 licence) to show countries and cities.
              </div>
            )}
            {secSummary && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[['Sign-ins (24h)', secSummary.sign_ins, 'text-emerald-400'], ['Failed sign-ins', secSummary.failed_sign_ins, 'text-rose-400'],
                  ['Sign-ups', secSummary.sign_ups, 'text-sky-400'], ['Unique IPs', secSummary.unique_ips, 'text-white'],
                  ['Admin actions', secSummary.admin_actions, 'text-purple-400']].map(([label, value, tone]) => (
                  <div key={label} className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">{label}</p>
                    <p className={`text-2xl font-black mt-1 ${tone}`}>{value}</p>
                  </div>
                ))}
              </div>
            )}
            {secSummary && (
              <div className="grid lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-5">
                  <h3 className="font-black text-white">Suspicious IPs <span className="text-slate-500 font-medium text-sm">· 5+ failed sign-ins in 24h</span></h3>
                  {secSummary.suspicious_ips.length === 0 ? <p className="text-slate-500 text-sm mt-3">Nothing suspicious in the last 24 hours.</p> : (
                    <table className="w-full text-sm mt-3">
                      <thead><tr className="text-left text-xs uppercase tracking-widest text-slate-500">
                        <th className="py-2">IP address</th><th>Failures</th><th>Accounts tried</th><th>Country</th><th>Last seen</th><th></th></tr></thead>
                      <tbody className="divide-y divide-slate-800">
                        {secSummary.suspicious_ips.map(s => (
                          <tr key={s.ip}>
                            <td className="py-2 font-mono text-rose-300">{s.ip}</td><td className="font-bold text-white">{s.failures}</td>
                            <td className="text-slate-300">{s.accounts}</td><td className="text-slate-400">{s.country || '—'}</td>
                            <td className="text-slate-400 text-xs">{new Date(s.last_seen).toLocaleString()}</td>
                            <td><button onClick={() => applySecFilter({ ip: s.ip, q: '', event: '' })} className="text-xs font-bold text-sky-400 hover:underline">Show events</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                  <h3 className="font-black text-white">Sign-ins by country <span className="text-slate-500 font-medium text-sm">· 24h</span></h3>
                  {secSummary.top_countries.length === 0 ? <p className="text-slate-500 text-sm mt-3">No located sign-ins yet.</p> : (
                    <ul className="mt-3 space-y-2">
                      {secSummary.top_countries.map(c => (
                        <li key={c.country} className="flex justify-between text-sm"><span className="text-slate-300">{c.country}</span><span className="font-bold text-white">{c.sign_ins}</span></li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl">
              <div className="p-4 flex flex-wrap gap-2 items-center border-b border-slate-800">
                <h3 className="font-black text-white mr-auto">Event log</h3>
                <select aria-label="Event type" value={secFilter.event} onChange={e => applySecFilter({ event: e.target.value })}
                  className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white">
                  <option value="">All events</option>
                  {Object.entries(secSummary?.event_types || {}).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                </select>
                <form onSubmit={e => { e.preventDefault(); applySecFilter({ q: e.target.elements.q.value, ip: '' }); }} className="flex gap-2">
                  <input name="q" defaultValue={secFilter.q} placeholder="Email, IP, country or city"
                    className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder:text-slate-500 w-64" />
                  <button className="text-xs font-black px-3 py-2 rounded-xl bg-slate-700 text-white hover:bg-slate-600">Search</button>
                </form>
                {(secFilter.event || secFilter.q || secFilter.ip) && (
                  <button onClick={() => applySecFilter({ event: '', q: '', ip: '' })} className="text-xs font-bold text-slate-400 hover:text-white">
                    Clear filters{secFilter.ip ? ` (IP ${secFilter.ip})` : ''}
                  </button>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/50"><tr>{['Time', 'Event', 'Account', 'IP address', 'Location', 'Device', 'Details'].map(c => (
                    <th key={c} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{c}</th>))}</tr></thead>
                  <tbody className="divide-y divide-slate-800">
                    {secEvents.map(e => (
                      <tr key={e.id} className="hover:bg-slate-800/30 align-top">
                        <td className="px-4 py-2.5 text-slate-400 text-xs whitespace-nowrap">{new Date(e.ts).toLocaleString()}</td>
                        <td className="px-4 py-2.5"><span className={`text-xs font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${EVENT_TONE[e.event] || 'bg-slate-700 text-slate-300'}`}>{e.label}</span>
                          {e.portal && <span className="ml-1 text-[10px] uppercase text-slate-500">{e.portal}</span>}</td>
                        <td className="px-4 py-2.5 text-slate-300">{e.email || '—'}</td>
                        <td className="px-4 py-2.5">{e.ip ? <button onClick={() => applySecFilter({ ip: e.ip, q: '', event: '' })} className="font-mono text-sky-300 hover:underline">{e.ip}</button> : '—'}</td>
                        <td className="px-4 py-2.5 text-slate-400">{e.location || '—'}</td>
                        <td className="px-4 py-2.5 text-slate-400 text-xs" title={e.user_agent || ''}>{device(e.user_agent)}</td>
                        <td className="px-4 py-2.5 text-slate-500 text-xs">{e.details ? Object.entries(e.details).filter(([, v]) => v && typeof v !== 'object').map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join(' · ') : ''}</td>
                      </tr>
                    ))}
                    {!secLoading && secEvents.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">No security events match.</td></tr>}
                  </tbody>
                </table>
              </div>
              {secNext && (
                <div className="p-4 border-t border-slate-800 text-center">
                  <button onClick={() => loadSecurityEvents(secFilter, secNext)} disabled={secLoading} className="text-xs font-black px-4 py-2 rounded-xl bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50">
                    {secLoading ? 'Loading…' : 'Load older events'}
                  </button>
                </div>
              )}
            </div>
          </section>
        )}

        {tab === 'hr' && (
          <section className="max-w-6xl space-y-4">
            <p className="text-slate-400 text-sm">
              Employer accounts waiting for approval. Approved employers can post jobs and review applicants.
              An employer must verify their email before they can be approved.
            </p>
            {hrError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm font-bold">{hrError}</div>
            )}
            {pendingHR === null ? (
              !hrError && <p className="text-slate-500 text-sm">Loading…</p>
            ) : pendingHR.length === 0 ? (
              <p className="text-slate-500 text-sm">No employer accounts are waiting for approval.</p>
            ) : (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/50">
                    <tr>{['Name', 'Work email', 'Company', 'Country', 'Signed up', 'Email', 'Action'].map(col => (
                      <th key={col} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{col}</th>
                    ))}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {pendingHR.map(account => (
                      <tr key={account.id} className="hover:bg-slate-800/30">
                        <td className="px-4 py-3 font-semibold text-white">{account.full_name || '—'}</td>
                        <td className="px-4 py-3 text-slate-400">{account.email}</td>
                        <td className="px-4 py-3 text-slate-300">{account.company_name || '—'}</td>
                        <td className="px-4 py-3 text-slate-400">{account.country || '—'}</td>
                        <td className="px-4 py-3 text-slate-400 text-xs">
                          {account.created_at ? new Date(account.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {account.is_verified === undefined ? (
                            <span className="text-xs text-slate-500">—</span>
                          ) : (
                            <span className={`text-xs font-black px-2 py-0.5 rounded-full ${
                              account.is_verified ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                            }`}>{account.is_verified ? 'Verified' : 'Not verified'}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <button onClick={() => approveHR(account)}
                            disabled={approving === account.id || account.is_verified === false}
                            title={account.is_verified === false ? 'The employer must verify their email first' : undefined}
                            className="text-xs font-black px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white disabled:bg-slate-700 disabled:text-slate-400 disabled:cursor-not-allowed">
                            {approving === account.id ? 'Approving…' : 'Approve'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {tab === 'automation' && (
          <section className="max-w-5xl bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <h2 className="text-xl font-bold">Jobs and notifications</h2>
            <p className="text-sm text-slate-300">Scraper monitoring, daily admin summaries, matching job alerts and internal application notifications. Your existing cron service continues to scrape jobs.</p>
            <div className="flex gap-3">
              <button type="button" onClick={() => load('automation')} className="rounded-xl border border-slate-600 px-4 py-2 font-bold">Refresh status</button>
              <button type="button" onClick={processNotifications} disabled={processing}
                className="rounded-xl bg-emerald-700 px-4 py-2 font-bold disabled:opacity-50">
                {processing ? 'Processing…' : 'Process queued notifications'}
              </button>
            </div>
            {automationError && <p role="alert" className="text-rose-300">{automationError}</p>}
            {automation && <>
              <p className="text-sm text-slate-200">Job and admin alerts: {automation.events_configured ? 'Configured' : 'Not configured'} · Internal applications: {automation.application_notifications_configured ? 'Configured' : 'Not configured'}</p>
              <p className="text-sm text-slate-400">Configuration status does not confirm delivery. Confirm accepted emails in n8n and Resend.</p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {['pending', 'processing', 'sent', 'failed', 'cancelled'].map(status => (
                  <div key={status} className="bg-slate-950 p-3 rounded-xl">
                    <p className="text-2xl font-bold">{automation.notification_counts[status] || 0}</p>
                    <p className="text-sm text-slate-300">{status === 'sent' ? 'Provider accepted' : status}</p>
                  </div>
                ))}
              </div>
              {automation.last_scrape ? <>
                <p className="text-sm">Latest scrape: <strong>{automation.last_scrape.status}</strong> · Started {new Date(`${automation.last_scrape.started_at}Z`).toLocaleString()}</p>
                <p className="text-sm text-slate-300">Fetched {automation.last_scrape.summary.total_scraped || 0} · Saved {automation.last_scrape.summary.total_saved || 0} · Failed sources {automation.last_scrape.summary.failed_sources || 0}</p>
                <div className="overflow-auto max-h-80">
                  <table className="w-full text-sm text-left">
                    <thead className="text-slate-300"><tr><th className="p-2">Source</th><th className="p-2">Result</th><th className="p-2">Jobs fetched</th></tr></thead>
                    <tbody>{(automation.last_scrape.summary.source_results || []).map(source => (
                      <tr key={source.name} className="border-t border-slate-800"><td className="p-2">{source.name}</td><td className="p-2">{source.status}</td><td className="p-2">{source.job_count}</td></tr>
                    ))}</tbody>
                  </table>
                </div>
              </> : <p className="text-sm text-amber-300">No scrape has been recorded since this update. The next cron run will appear here.</p>}
              {!!automation.failed_notifications.length && <div>
                <h3 className="font-bold text-rose-300">Notifications needing attention</h3>
                <p className="text-sm text-slate-300">Fix the reported configuration or provider error. Expired retries stop automatically to avoid sending duplicate emails.</p>
                <ul className="mt-2 text-sm text-slate-300 space-y-1">{automation.failed_notifications.map(event => (
                  <li key={event.event_id}>{event.event_type}: {event.event_id} · {event.last_error} · {event.attempts} attempts</li>
                ))}</ul>
              </div>}
            </>}
          </section>
        )}

        {tab === 'ai' && (
          <section className="max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <h2 className="text-xl font-bold">AI Resume Test</h2>
            <p className="mt-2 text-sm text-slate-400">
              Test resume extraction with a fictional candidate. No user resume is uploaded and no resume scan is deducted.
              The test uses your configured AI provider and may take several minutes.
            </p>
            <button type="button" onClick={testAI} disabled={testingAI}
              className="mt-4 px-4 py-2 rounded-xl bg-emerald-600 disabled:bg-slate-700 font-bold">
              {testingAI ? 'Testing resume extraction…' : 'Run AI Test'}
            </button>
            <div role="status" aria-live="polite" className="mt-4">
              {aiError && <p className="text-rose-400">{aiError}</p>}
              {aiReport && <p className={aiReport.passed ? 'text-emerald-400' : 'text-amber-400'}>
                {aiReport.passed ? 'Synthetic extraction passed. A real resume still needs verification.' : 'Synthetic extraction failed. Copy the report below for investigation.'}
              </p>}
            </div>
            {aiReport && (
              <>
                <button type="button" className="mt-3 text-sm text-emerald-400"
                  onClick={async () => {
                    try { await navigator.clipboard.writeText(JSON.stringify(aiReport, null, 2)); setMsg('Diagnostic report copied'); }
                    catch { setAIError('Could not copy automatically. Select and copy the report below.'); }
                  }}>Copy diagnostic report</button>
                <pre className="mt-3 p-4 bg-slate-950 rounded-xl text-xs whitespace-pre-wrap break-words overflow-auto max-h-[36rem]">
                  {JSON.stringify(aiReport, null, 2)}
                </pre>
              </>
            )}
          </section>
        )}

        {/* Stats */}
        {tab === 'stats' && stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ['Total Users', stats.total_users, 'text-blue-400'],
              ['Total Jobs', stats.total_jobs, 'text-emerald-400'],
              ['Applications', stats.total_applications, 'text-purple-400'],
              ['Resumes', stats.total_resumes, 'text-amber-400'],
              ['HR Users', stats.hr_users, 'text-pink-400'],
              ['HR Posted Jobs', stats.hr_posted_jobs, 'text-cyan-400'],
              ['New Users Today', stats.new_users_today, 'text-green-400'],
            ].map(([label, value, color]) => (
              <div key={label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <div className={`text-3xl font-black ${color}`}>{value ?? 0}</div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-1">{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Users */}
        {tab === 'users' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50">
                <tr>{['Name','Email','Country','Track','Role','Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {users.map(u => (
                  <tr key={u.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-semibold text-white">{u.full_name || '—'}</td>
                    <td className="px-4 py-3 text-slate-400">{u.email}</td>
                    <td className="px-4 py-3 text-slate-400">{u.country || '—'}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{u.career_track || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-black px-2 py-0.5 rounded-full ${
                        u.is_admin ? 'bg-purple-500/20 text-purple-400'
                        : u.is_hr ? 'bg-blue-500/20 text-blue-400'
                        : 'bg-slate-700 text-slate-400'
                      }`}>{u.is_admin ? 'Admin' : u.is_hr ? 'HR' : 'User'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {!u.is_hr && !u.is_admin && (
                          <button onClick={() => makeHR(u.id)}
                            className="text-xs font-bold px-2 py-1 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20">
                            Make HR
                          </button>
                        )}
                        <button onClick={() => delUser(u.id)}
                          className="text-xs font-bold px-2 py-1 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Jobs */}
        {tab === 'jobs' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50">
                <tr>{['Title','Company','Location','Source','Work Type','Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {jobs.map(j => (
                  <tr key={j.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-semibold text-white">{j.title}</td>
                    <td className="px-4 py-3 text-slate-400">{j.company}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{j.location || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${j.posted_by_hr ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-700 text-slate-400'}`}>
                        {j.source || 'Scraped'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 capitalize text-xs">{j.work_type || '—'}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => delJob(j.id)}
                        className="text-xs font-bold px-2 py-1 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Applications */}
        {tab === 'apps' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50">
                <tr>{['Applicant','Job','Company','ATS','Status','Date'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {apps.map(a => (
                  <tr key={a.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 text-white font-semibold text-xs">{a.user_email}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{a.job_title || '—'}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{a.company || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-black px-2 py-0.5 rounded-full ${
                        (a.ats_score||0) >= 80 ? 'bg-emerald-500/20 text-emerald-400'
                        : (a.ats_score||0) >= 60 ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-slate-700 text-slate-400'
                      }`}>{a.ats_score || 0}%</span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 capitalize text-xs">{a.status}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{new Date(a.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
