import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Ban, CheckCircle2, Download, Search } from 'lucide-react';
import { adminDelete, adminGet, adminPost, ago, device, downloadCsv, eventTone, message, num, when } from '../adminApi';
import MfaSetup from '../MfaSetup';
import SignupRules from '../SignupRules';
import { Banner, Button, Chip, Empty, SectionHeader, Segmented, Stat, Td, Th, card } from '../ui';

const CATEGORIES = [['', 'All'], ['signins', 'Sign-ins'], ['failures', 'Failures'], ['signups', 'Sign-ups'],
  ['account', 'Account changes'], ['admin', 'Admin actions']];

function Posture({ posture }) {
  const tone = posture.score >= 85 ? '#10b981' : posture.score >= 60 ? '#f59e0b' : '#e11d48';
  return (
    <div className={`${card} p-5 flex flex-col sm:flex-row sm:items-center gap-5`}>
      <div className="relative w-24 h-24 shrink-0" role="img" aria-label={`Security score ${posture.score} out of 100`}>
        <svg viewBox="0 0 36 36" className="w-24 h-24 -rotate-90">
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="#f1f5f9" strokeWidth="3.2" />
          <circle cx="18" cy="18" r="15.9" fill="none" stroke={tone} strokeWidth="3.2" strokeLinecap="round"
            strokeDasharray={`${posture.score} 100`} />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div><div className="text-2xl font-semibold">{posture.score}</div><div className="text-[10px] text-slate-500 -mt-1">/ 100</div></div>
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-slate-900">Security posture</div>
        <ul className="mt-2 grid sm:grid-cols-2 xl:grid-cols-3 gap-x-6 gap-y-2 text-[13px]">
          {posture.checks.map(c => (
            <li key={c.label} className={`flex items-start gap-2 ${c.ok ? 'text-emerald-700' : 'text-amber-800'}`} title={c.hint || ''}>
              {c.ok ? <CheckCircle2 size={15} className="mt-0.5 shrink-0" /> : <AlertTriangle size={15} className="mt-0.5 shrink-0" />}
              <span>{c.label}{c.hint && <span className="block text-xs text-amber-700/80">{c.hint}</span>}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function SecurityTab({ summary, reload, notify, confirm, focus }) {
  const [filter, setFilter] = useState({ category: focus === 'failures' ? 'failures' : '', q: '', ip: '' });
  const [query, setQuery] = useState('');
  const [events, setEvents] = useState([]);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async (f, before = null) => {
    setLoading(true); setError('');
    try {
      const params = { limit: 25, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) };
      if (before) params.before_id = before;
      const data = await adminGet('/admin/security/events', params);
      setEvents(prev => (before ? [...prev, ...data.events] : data.events));
      setNext(data.next_before_id);
    } catch (err) { setError(message(err, 'Could not load security events.')); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(filter); }, [filter, load]);

  const apply = (change) => setFilter(f => ({ ...f, ...change }));
  const blocked = (ip) => summary.blocked_ips.some(b => b.ip === ip && b.active);

  const blockIp = (ip) => confirm({
    title: `Block ${ip}?`, tone: 'red', confirmLabel: 'Block IP',
    body: 'Sign-ins and sign-ups from this address will be refused. Existing sessions are not ended; suspend accounts or sign them out separately.',
    reasonLabel: 'Reason (kept in the audit log)', reasonPlaceholder: 'e.g. password spraying against several accounts',
    onConfirm: async (reason) => { await adminPost('/admin/security/blocked-ips', { ip, reason }); notify(`${ip} blocked`); reload(); },
    errorText: (err) => message(err, 'Could not block this IP.'),
  });
  const unblock = (ip) => confirm({
    title: `Unblock ${ip}?`, confirmLabel: 'Unblock',
    onConfirm: async () => { await adminDelete(`/admin/security/blocked-ips/${encodeURIComponent(ip)}`); notify(`${ip} unblocked`); reload(); },
    errorText: (err) => message(err, 'Could not unblock this IP.'),
  });
  const exportCsv = async () => {
    setExporting(true);
    try { await downloadCsv('/admin/security/events.csv', Object.fromEntries(Object.entries(filter).filter(([, v]) => v)), 'security-events.csv'); }
    catch (err) { setError(message(err, 'Could not export events.')); }
    finally { setExporting(false); }
  };

  const activeBlocks = summary.blocked_ips.filter(b => b.active);
  const maxCountry = Math.max(1, ...summary.top_countries.map(c => c.sign_ins));

  return (
    <div className="space-y-4">
      {!summary.geolocation_enabled && (
        <Banner tone="amber">Location lookup is off, so events show IP addresses without a country or city.
          Set <code className="font-mono">MAXMIND_LICENSE_KEY</code> on Railway (free GeoLite2 licence) to turn it on.</Banner>
      )}
      <Posture posture={summary.posture} />
      <div className="grid sm:grid-cols-3 gap-4">
        <Stat label="Sign-ins (24 h)" value={num(summary.sign_ins)} hint={`from ${num(summary.unique_ips)} IP addresses`} />
        <Stat label="Failed sign-ins (24 h)" value={num(summary.failed_sign_ins)} highlight={summary.suspicious_ips.length > 0}
          hint={summary.suspicious_ips.length ? `${summary.suspicious_ips.length} suspicious IP(s)` : 'No suspicious IPs'} />
        <Stat label="Active sessions" value={num(summary.active_sessions)} hint={`${num(summary.admin_actions)} admin action(s) today`} />
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <div className={`${card} xl:col-span-2 overflow-hidden`}>
          <SectionHeader title="Suspicious IPs" subtitle="5 or more failed sign-ins in the last 24 hours" />
          {summary.suspicious_ips.length === 0 ? <Empty>Nothing suspicious in the last 24 hours.</Empty> : (
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr><Th>IP address</Th><Th>Location</Th><Th>Failures</Th><Th>Accounts tried</Th><Th>Last seen</Th><Th right>Action</Th></tr></thead>
              <tbody>{summary.suspicious_ips.map(s => (
                <tr key={s.ip}>
                  <Td className="font-mono">{s.ip}</Td><Td>{s.country || '—'}</Td>
                  <Td><Chip tone={s.failures >= 20 ? 'red' : 'amber'}>{s.failures}</Chip></Td>
                  <Td>{s.accounts}</Td><Td className="text-slate-500">{ago(s.last_seen)}</Td>
                  <Td className="text-right whitespace-nowrap space-x-1">
                    <Button size="sm" onClick={() => { setQuery(''); apply({ ip: s.ip, q: '', category: '' }); }}>Investigate</Button>
                    {blocked(s.ip) || s.blocked ? <Chip tone="red">Blocked</Chip>
                      : <Button size="sm" variant="danger" icon={Ban} onClick={() => blockIp(s.ip)}>Block IP</Button>}
                  </Td>
                </tr>))}
              </tbody>
            </table></div>
          )}
          {activeBlocks.length > 0 && (
            <div className="border-t border-slate-100 px-5 py-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Blocked IP addresses</div>
              <ul className="space-y-1.5 text-sm">
                {activeBlocks.map(b => (
                  <li key={b.ip} className="flex flex-wrap items-center gap-2">
                    <span className="font-mono">{b.ip}</span>
                    <span className="text-slate-500 text-xs">{b.reason || 'No reason given'} · by {b.created_by} · {b.expires_at ? `until ${when(b.expires_at)}` : 'until removed'}</span>
                    <button type="button" onClick={() => unblock(b.ip)} className="ml-auto text-xs font-semibold text-slate-700 hover:underline">Unblock</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className={card}>
          <SectionHeader title="Sign-ins by country" subtitle="Last 24 hours" />
          <div className="px-5 pb-5 space-y-3 text-sm">
            {summary.top_countries.length === 0 && <p className="text-slate-500">No located sign-ins yet.</p>}
            {summary.top_countries.map(c => (
              <div key={c.country}>
                <div className="flex justify-between"><span>{c.country}</span><span className="font-medium">{num(c.sign_ins)}</span></div>
                <div className="h-2 mt-1 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${(c.sign_ins * 100) / maxCountry}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <SignupRules notify={notify} confirm={confirm} />

      <div className={`${card} overflow-hidden`}>
        <SectionHeader title="Event log" subtitle={`Visible to admins only · every view is recorded · kept ${summary.retention_days} days`}>
          <Segmented options={CATEGORIES} value={filter.category} onChange={category => apply({ category })} />
          <form onSubmit={e => { e.preventDefault(); apply({ q: query.trim(), ip: '' }); }} className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Email, IP, city or country" aria-label="Search events"
              className="pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg w-60 focus:outline-none focus:ring-2 focus:ring-emerald-500/40" />
          </form>
          <Button icon={Download} busy={exporting} onClick={exportCsv}>CSV</Button>
        </SectionHeader>
        {(filter.ip || filter.q) && (
          <div className="px-5 pb-3 -mt-1 text-xs text-slate-600 flex items-center gap-2">
            Filtered by {filter.ip ? <>IP <span className="font-mono">{filter.ip}</span></> : <>“{filter.q}”</>}
            {filter.ip && !blocked(filter.ip) && <button type="button" onClick={() => blockIp(filter.ip)} className="font-semibold text-rose-700 hover:underline">Block this IP</button>}
            <button type="button" onClick={() => { setQuery(''); apply({ ip: '', q: '' }); }} className="font-semibold text-slate-700 hover:underline">Clear</button>
          </div>
        )}
        {error && <div className="px-5 pb-3"><Banner onClose={() => setError('')}>{error}</Banner></div>}
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><Th>Time</Th><Th>Event</Th><Th>Account</Th><Th>IP address</Th><Th>Location</Th><Th>Device</Th><Th>Details</Th></tr></thead>
          <tbody>
            {events.map(e => (
              <tr key={e.id} className="hover:bg-slate-50/60">
                <Td className="text-slate-500 whitespace-nowrap" title={when(e.ts)}>{ago(e.ts)}</Td>
                <Td><Chip tone={eventTone(e.event)}>{e.label}</Chip>{e.portal && <span className="ml-1.5 text-[10px] uppercase text-slate-400">{e.portal}</span>}</Td>
                <Td>{e.email || '—'}</Td>
                <Td>{e.ip ? <button type="button" onClick={() => { setQuery(''); apply({ ip: e.ip, q: '' }); }} className="font-mono text-[12.5px] text-slate-800 hover:text-emerald-700 hover:underline">{e.ip}</button> : '—'}</Td>
                <Td>{e.location || '—'}</Td>
                <Td className="text-slate-500 whitespace-nowrap" title={e.user_agent || ''}>{device(e.user_agent)}</Td>
                <Td className="text-slate-500 text-xs max-w-xs">{e.details ? Object.entries(e.details).filter(([, v]) => v && typeof v !== 'object')
                  .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${String(v).replace(/_/g, ' ')}`).join(' · ') : ''}</Td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {!loading && events.length === 0 && <Empty>No security events match.</Empty>}
        {next && (
          <div className="px-5 py-3 border-t border-slate-100 text-right">
            <Button size="sm" busy={loading} onClick={() => load(filter, next)}>Load older events</Button>
          </div>
        )}
      </div>

      <MfaSetup required />
    </div>
  );
}
