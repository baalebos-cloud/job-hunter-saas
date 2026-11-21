import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, XCircle } from 'lucide-react';
import { adminGet, adminPost, ago, initials, message } from '../adminApi';
import { Banner, Button, Chip, Empty, Segmented, Spinner, card } from '../ui';

const CHECK = {
  ok: { icon: CheckCircle2, tone: 'green' }, warn: { icon: AlertTriangle, tone: 'amber' }, risk: { icon: XCircle, tone: 'red' },
};

function link(url) {
  if (!url) return null;
  const href = /^https?:\/\//i.test(url) ? url : `https://${url}`;
  return <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-emerald-700 hover:underline break-all">
    {url.replace(/^https?:\/\/(www\.)?/i, '').replace(/\/$/, '')}<ExternalLink size={12} /></a>;
}

function EmployerCard({ e, onApprove, onReject, busy }) {
  const ring = e.risk === 'risk' ? 'ring-1 ring-rose-200 border-rose-200' : '';
  return (
    <article className={`${card} ${ring} p-5 flex flex-col`}>
      <div className="flex items-start gap-3">
        <div className={`w-11 h-11 shrink-0 rounded-xl grid place-items-center font-semibold ${e.risk === 'risk' ? 'bg-rose-50 text-rose-700' : 'bg-blue-50 text-blue-700'}`}>
          {initials(e.company_name, e.email)}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 truncate">{e.company_name || 'Unnamed company'}</h3>
          <p className="text-[13px] text-slate-500 truncate">{[e.full_name, e.job_title].filter(Boolean).join(' · ') || '—'}</p>
        </div>
        <Chip tone={e.status === 'pending' && Date.now() - new Date(e.created_at) > 86400000 ? 'amber' : 'slate'}>{ago(e.created_at)}</Chip>
      </div>
      <dl className="mt-4 space-y-2 text-[13px]">
        {[['Work email', e.email], ['Website', link(e.company_url) || <span className="text-slate-400">none given</span>],
          ['LinkedIn', link(e.linkedin_url) || <span className="text-slate-400">none given</span>], ['Country', e.country || '—'],
          ['Signed up from', e.signup_location || e.signup_ip ? <>{e.signup_location}{e.signup_location && e.signup_ip ? ' · ' : ''}
            {e.signup_ip && <span className="font-mono text-xs">{e.signup_ip}</span>}</> : '—'],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4"><dt className="text-slate-500 shrink-0">{label}</dt><dd className="text-right min-w-0 truncate">{value}</dd></div>
        ))}
      </dl>
      <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Automatic checks">
        {e.checks.map(c => { const { icon: Icon, tone } = CHECK[c.level]; return <li key={c.label}><Chip tone={tone}><Icon size={12} />{c.label}</Chip></li>; })}
      </ul>
      {e.rejected_reason && <p className="mt-3 text-xs text-rose-700">Rejected: {e.rejected_reason}</p>}
      <div className="mt-auto pt-5 flex gap-2">
        {e.status !== 'approved' && (
          <Button variant="primary" className="flex-1" busy={busy === e.id} disabled={!e.is_verified}
            title={e.is_verified ? undefined : 'The employer must verify their email first'} onClick={() => onApprove(e)}>
            {e.status === 'rejected' ? 'Approve anyway' : 'Approve'}
          </Button>
        )}
        {e.status !== 'rejected' && (
          <Button className="flex-1" onClick={() => onReject(e)}>{e.status === 'approved' ? 'Revoke access…' : 'Reject…'}</Button>
        )}
      </div>
    </article>
  );
}

export default function EmployersTab({ notify, confirm, onChanged }) {
  const [status, setStatus] = useState('pending');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(null);

  const load = useCallback(async (s) => {
    setError('');
    try { setData(await adminGet('/admin/employers', { status: s })); }
    catch (err) { setError(message(err, 'Could not load employers.')); }
  }, []);
  useEffect(() => { setData(null); load(status); }, [status, load]);

  const approve = (e) => confirm({
    title: `Approve ${e.company_name || e.email}?`, confirmLabel: 'Approve',
    body: e.risk === 'risk' ? <Banner tone="red">This application has high-risk checks. Approve only if you have confirmed the company.</Banner>
      : 'They will receive an email and can post jobs immediately.',
    onConfirm: async () => {
      setBusy(e.id);
      try { await adminPost(`/hr-auth/approve/${e.id}`); notify(`${e.company_name || e.email} approved`); await load(status); onChanged(); }
      finally { setBusy(null); }
    },
    errorText: (err) => message(err, 'Could not approve this employer.'),
  });
  const reject = (e) => confirm({
    title: e.status === 'approved' ? `Revoke ${e.company_name || e.email}?` : `Reject ${e.company_name || e.email}?`,
    tone: 'red', confirmLabel: e.status === 'approved' ? 'Revoke access' : 'Reject',
    body: 'They are signed out and cannot use the employer portal. They are emailed the reason below.',
    reasonLabel: 'Reason (sent to the applicant)', reasonPlaceholder: 'e.g. Please sign up with a work email on your company domain.',
    defaultReason: e.checks.filter(c => c.level === 'risk').map(c => c.label).join('; '),
    onConfirm: async (reason) => { await adminPost(`/hr-auth/reject/${e.id}`, { reason, notify: true }); notify(`${e.company_name || e.email} rejected`); await load(status); onChanged(); },
    errorText: (err) => message(err, 'Could not reject this employer.'),
  });

  const counts = data?.counts || {};
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented size="md" value={status} onChange={setStatus}
          options={[['pending', `Pending${counts.pending !== undefined ? ` (${counts.pending})` : ''}`],
            ['approved', `Approved${counts.approved !== undefined ? ` (${counts.approved})` : ''}`],
            ['rejected', `Rejected${counts.rejected !== undefined ? ` (${counts.rejected})` : ''}`]]} />
        <span className="text-sm text-slate-500">Approved employers get an email and can post jobs immediately.</span>
      </div>
      {error && <Banner onClose={() => setError('')}>{error}</Banner>}
      {!data && !error && <Spinner />}
      {data && data.items.length === 0 && <div className={card}><Empty>No {status} employer accounts.</Empty></div>}
      {data && data.items.length > 0 && (
        <div className="grid md:grid-cols-2 2xl:grid-cols-3 gap-4">
          {data.items.map(e => <EmployerCard key={e.id} e={e} onApprove={approve} onReject={reject} busy={busy} />)}
        </div>
      )}
    </div>
  );
}
