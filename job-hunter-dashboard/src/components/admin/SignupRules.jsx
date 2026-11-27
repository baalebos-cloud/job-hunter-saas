/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useCallback, useEffect, useState } from 'react';
import { Building2, MailX, Trash2 } from 'lucide-react';
import { adminDelete, adminGet, adminPost, ago, message } from './adminApi';
import { Banner, Button, SectionHeader, card } from './ui';

const KINDS = {
  allowed_network: { title: 'Trusted networks', icon: Building2, placeholder: 'e.g. 102.89.33.0/24',
    hint: 'Offices, schools or bootcamps where several people sign up from one network. Up to a /20 range.' },
  blocked_domain: { title: 'Extra blocked email domains', icon: MailX, placeholder: 'e.g. newtempmail.io',
    hint: 'Temporary-email domains that are not on the built-in list yet.' },
};

function RuleList({ kind, rules, onAdd, onRemove }) {
  const meta = KINDS[kind];
  const [value, setValue] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    if (await onAdd(kind, value, note)) { setValue(''); setNote(''); }
    setBusy(false);
  };
  return (
    <div className="p-5 space-y-3">
      <div className="flex items-center gap-2 font-medium text-slate-900"><meta.icon size={16} />{meta.title}</div>
      <p className="text-xs text-slate-500">{meta.hint}</p>
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <input value={value} onChange={e => setValue(e.target.value)} placeholder={meta.placeholder} aria-label={meta.title} required
          className="flex-1 min-w-[10rem] text-sm border border-slate-200 rounded-lg px-3 py-2 font-mono" />
        <input value={note} onChange={e => setNote(e.target.value)} placeholder="Note (optional)" aria-label={`Note for ${meta.title}`}
          className="flex-1 min-w-[10rem] text-sm border border-slate-200 rounded-lg px-3 py-2" />
        <Button type="submit" variant="primary" busy={busy}>Add</Button>
      </form>
      <ul className="divide-y divide-slate-100 text-sm">
        {rules.length === 0 && <li className="py-2 text-slate-500">None yet.</li>}
        {rules.map(r => (
          <li key={r.id} className="py-2 flex items-center gap-3">
            <span className="font-mono text-slate-900">{r.value}</span>
            <span className="text-xs text-slate-500 truncate flex-1">{[r.note, `added ${ago(r.created_at)}`].filter(Boolean).join(' · ')}</span>
            <button type="button" onClick={() => onRemove(r)} aria-label={`Remove ${r.value}`} className="p-1.5 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={15} /></button>
          </li>))}
      </ul>
    </div>
  );
}

// Owner console → Security: who may create accounts.
export default function SignupRules({ notify, confirm }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(() => adminGet('/admin/signup-rules').then(setData).catch(err => setError(message(err, 'Sign-up rules could not be loaded.'))), []);
  useEffect(() => { load(); }, [load]);

  const add = async (kind, value, note) => {
    try {
      await adminPost('/admin/signup-rules', { kind, value, note });
      notify(`${value.trim()} added`); setError(''); load(); return true;
    } catch (err) { setError(message(err, 'The rule could not be added.')); return false; }
  };
  const remove = (rule) => confirm({
    title: `Remove ${rule.value}?`,
    body: rule.kind === 'allowed_network' ? 'New sign-ups from this network go back to one account per 30 days.'
      : 'Addresses at this domain can sign up again, unless the built-in list blocks them.',
    confirmLabel: 'Remove', tone: 'red',
    errorText: (err) => message(err, 'The rule could not be removed.'),
    onConfirm: async () => { await adminDelete(`/admin/signup-rules/${rule.id}`); notify(`${rule.value} removed`); load(); },
  });

  return (
    <section className={`${card} overflow-hidden`} aria-label="Sign-up rules">
      <SectionHeader title="Sign-up rules"
        subtitle={data ? `One new candidate account per network or device every ${data.one_account_days} days · ${data.bundled_blocked_domains.toLocaleString()} temporary-email domains blocked automatically · free scans are shared by accounts from the same network or device`
          : 'Loading…'} />
      {error && <div className="px-5"><Banner onClose={() => setError('')}>{error}</Banner></div>}
      {data && (
        <div className="grid md:grid-cols-2 md:divide-x divide-slate-100 border-t border-slate-100">
          <RuleList kind="allowed_network" rules={data.rules.filter(r => r.kind === 'allowed_network')} onAdd={add} onRemove={remove} />
          <RuleList kind="blocked_domain" rules={data.rules.filter(r => r.kind === 'blocked_domain')} onAdd={add} onRemove={remove} />
        </div>)}
    </section>
  );
}
