import { useCallback, useEffect, useState } from 'react';
import { Activity, Briefcase, Building2, Cpu, Crown, Database, Hash, LayoutDashboard, LifeBuoy, Play, RefreshCw, ScrollText, ShieldAlert, Users } from 'lucide-react';
import { adminGet, adminPost, ago, message, needsMfaEnrollment } from './adminApi';
import MfaSetup from './MfaSetup';
import { Banner, Button, ConfirmDialog, Spinner } from './ui';
import OverviewTab from './tabs/OverviewTab';
import SecurityTab from './tabs/SecurityTab';
import EmployersTab from './tabs/EmployersTab';
import UsersTab from './tabs/UsersTab';
import JobsTab from './tabs/JobsTab';
import OperationsTab from './tabs/OperationsTab';
import AuditTab from './tabs/AuditTab';
import SupportTab from './tabs/SupportTab';
import SlackTab from './tabs/SlackTab';

const GRAFANA_URL = import.meta.env.VITE_GRAFANA_URL || '';
const TAB_ALIASES = { hr: 'employers', stats: 'overview', apps: 'jobs', automation: 'ops', ai: 'ops' };
const TABS = [
  ['overview', 'Overview', LayoutDashboard], ['security', 'Security', ShieldAlert], ['employers', 'Employers', Building2],
  ['users', 'Users', Users], ['jobs', 'Jobs & applications', Briefcase], ['support', 'Support', LifeBuoy], ['slack', 'Slack', Hash], ['ops', 'Operations', Cpu], ['audit', 'Audit log', ScrollText],
];

function initialTab() {
  const requested = new URLSearchParams(window.location.search).get('tab') || '';
  const id = TAB_ALIASES[requested] || requested;
  return TABS.some(([t]) => t === id) ? id : 'overview';
}

export default function AdminDashboard() {
  const [tab, setTab] = useState(initialTab);
  const [focus, setFocus] = useState(null);
  const [overview, setOverview] = useState(null);
  const [security, setSecurity] = useState(null);
  const [gate, setGate] = useState(null);          // 'mfa' | 'denied'
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [dialog, setDialog] = useState(null);
  const [scraping, setScraping] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const handle = useCallback((err, fallback) => {
    if (needsMfaEnrollment(err)) setGate('mfa');
    else if (err?.response?.status === 403) setGate('denied');
    else if (err?.response?.status === 401) window.location.href = '/login';
    else setError(message(err, fallback));
  }, []);

  const loadOverview = useCallback(async () => {
    try { setOverview(await adminGet('/admin/overview')); setGate(null); }
    catch (err) { handle(err, 'Could not load the Owner console.'); }
  }, [handle]);
  const loadSecurity = useCallback(async () => {
    try { setSecurity(await adminGet('/admin/security/summary')); }
    catch (err) { handle(err, 'Could not load security data.'); }
  }, [handle]);

  useEffect(() => {
    if (!localStorage.getItem('token')) { window.location.href = '/login'; return; }
    loadOverview();
  }, [loadOverview]);
  useEffect(() => { if (tab === 'security' && !gate) loadSecurity(); }, [tab, gate, loadSecurity]);
  useEffect(() => { if (!toast) return undefined; const t = setTimeout(() => setToast(''), 6000); return () => clearTimeout(t); }, [toast]);

  const goTo = (next, why = null) => {
    setTab(next); setFocus(why);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', next);
    window.history.replaceState(null, '', url);
  };
  const refresh = async () => { setRefreshing(true); await Promise.all([loadOverview(), tab === 'security' ? loadSecurity() : null]); setRefreshing(false); };
  const scrape = async () => {
    setScraping(true);
    try {
      const r = await adminPost('/admin/scrape', {}, { timeout: 600000 });
      setToast(`Scrape ${r.status || 'finished'}: ${r.total_saved ?? 0} new jobs saved.`);
      loadOverview();
    } catch (err) { setError(message(err, 'The scrape failed. Check Operations for source results.')); }
    finally { setScraping(false); }
  };

  if (gate === 'denied') return (
    <div className="max-w-lg mx-auto mt-16"><Banner>You do not have access to the Owner console. <a href="/" className="font-semibold underline">Back to dashboard</a></Banner></div>
  );
  if (gate === 'mfa') return (
    <div className="max-w-3xl mx-auto py-10 px-4 space-y-4">
      <div><h2 className="text-xl font-semibold tracking-tight text-slate-900">Set up two-step verification</h2>
        <p className="text-sm text-slate-600 mt-1">Admin accounts must use two-step verification. Set it up once to continue; you will be asked for a code each time you sign in.</p></div>
      <MfaSetup required onEnabled={() => { setGate(null); loadOverview(); }} />
    </div>
  );
  if (!overview) return error ? <div className="max-w-xl mx-auto mt-16"><Banner>{error} <button type="button" onClick={loadOverview} className="font-semibold underline">Retry</button></Banner></div> : <Spinner />;

  const sys = overview.system;
  const attention = Object.fromEntries(overview.attention.map(a => [a.kind, a]));
  const counts = {
    security: (security?.suspicious_ips?.length ?? (attention.suspicious_ips ? parseInt(attention.suspicious_ips.title, 10) : 0)) || 0,
    employers: overview.mix.employers_pending,
  };
  const duplicateCount = attention.duplicates ? parseInt(attention.duplicates.title, 10) : 0;
  const grafana = GRAFANA_URL || sys.grafana_url;

  return (
    <div className="-m-5 md:-m-9 min-h-full bg-slate-50 text-slate-900" style={{ fontFamily: "'Inter', sans-serif" }}>
      <header className="bg-white border-b border-slate-200 px-4 sm:px-8 pt-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold tracking-tight">Platform control centre</h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-violet-200"><Crown size={12} />Admin</span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-slate-500">
              <span className="flex items-center gap-1.5"><span className={`w-2 h-2 rounded-full ${sys.error_rate > 5 ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                API {sys.error_rate > 5 ? 'degraded' : 'healthy'}{sys.p95_ms != null ? ` · ${Math.round(sys.p95_ms)} ms p95` : ''}</span>
              {sys.db_pool_pct != null && <span className="flex items-center gap-1.5"><Database size={13} />DB pool {sys.db_pool_pct}%</span>}
              <span className="flex items-center gap-1.5"><RefreshCw size={13} />Last scrape {sys.last_scrape ? ago(sys.last_scrape.started_at) : 'not recorded'}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button icon={RefreshCw} busy={refreshing} onClick={refresh} aria-label="Refresh">Refresh</Button>
            {grafana && <a href={grafana} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-semibold rounded-lg px-3.5 py-2 border border-slate-200 bg-white hover:bg-slate-50"><Activity size={16} />Grafana</a>}
            <Button variant="primary" icon={Play} busy={scraping} onClick={scrape}>{scraping ? 'Scraping…' : 'Run scraper'}</Button>
          </div>
        </div>
        <nav className="mt-5 flex items-center gap-1 overflow-x-auto pb-3" aria-label="Owner console sections">
          {TABS.map(([id, label, Icon]) => (
            <button key={id} type="button" onClick={() => goTo(id)} aria-current={tab === id ? 'page' : undefined}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                tab === id ? 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}>
              <Icon size={16} />{label}
              {counts[id] > 0 && <span className="ml-0.5 text-[11px] font-bold px-1.5 rounded-full bg-rose-100 text-rose-700">{counts[id]}</span>}
            </button>
          ))}
        </nav>
      </header>

      <main className="px-4 sm:px-8 py-6 space-y-4">
        {toast && <Banner tone="green" onClose={() => setToast('')}>{toast}</Banner>}
        {error && <Banner onClose={() => setError('')}>{error}</Banner>}
        {tab === 'overview' && <OverviewTab data={overview} goTo={goTo} />}
        {tab === 'security' && (security ? <SecurityTab summary={security} reload={() => { loadSecurity(); loadOverview(); }}
          notify={setToast} confirm={setDialog} focus={focus} /> : <Spinner />)}
        {tab === 'employers' && <EmployersTab notify={setToast} confirm={setDialog} onChanged={loadOverview} />}
        {tab === 'users' && <UsersTab notify={setToast} confirm={setDialog} focus={focus} duplicateCount={duplicateCount} onChanged={loadOverview} />}
        {tab === 'jobs' && <JobsTab notify={setToast} confirm={setDialog} />}
        {tab === 'ops' && <OperationsTab system={sys} grafanaUrl={grafana} notify={setToast} onScrape={scrape} scraping={scraping} />}
        {tab === 'support' && <SupportTab notify={setToast} />}
        {tab === 'slack' && <SlackTab notify={setToast} />}
        {tab === 'audit' && <AuditTab />}
      </main>
      <ConfirmDialog dialog={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
