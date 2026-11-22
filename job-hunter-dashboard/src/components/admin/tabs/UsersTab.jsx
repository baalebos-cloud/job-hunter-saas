import { useCallback, useEffect, useState } from 'react';
import { Activity, Briefcase, Download, KeyRound, LogOut, PauseCircle, PlayCircle, Trash2, X } from 'lucide-react';
import { adminDelete, adminGet, adminPatch, adminPost, ago, device, downloadCsv, eventTone, initials, message, num, when } from '../adminApi';
import { Banner, Button, Chip, Empty, Menu, Pager, SearchInput, Segmented, Select, Spinner, Td, Th, card } from '../ui';

const ROLE = {
  super_admin: ['Super admin', 'violet'], security_auditor: ['Security auditor', 'violet'], engineering_lead: ['Engineering lead', 'violet'],
  compliance_officer: ['Compliance officer', 'violet'], viewer: ['Viewer', 'violet'], employer: ['Employer', 'blue'], candidate: ['Candidate', 'slate'],
};
const STATUS = {
  active: ['Active', 'green'], suspended: ['Suspended', 'red'], unverified: ['Unverified', 'slate'],
  awaiting_approval: ['Awaiting approval', 'amber'], rejected: ['Rejected', 'red'],
};
const REASON = {
  same_email: 'Same email address (ignoring dots, +tags and capitals)', same_phone: 'Same phone number',
  same_signup_ip: 'Several sign-ups from one IP address this week',
};

function ActivityDrawer({ user, onClose }) {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    adminGet('/admin/security/events', { user_id: user.id, limit: 50 }).then(d => setEvents(d.events))
      .catch(err => setError(message(err, 'Could not load activity.')));
  }, [user.id]);
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30" role="dialog" aria-modal="true" aria-label={`Activity for ${user.email}`} onClick={onClose}>
      <aside className="w-full max-w-xl h-full bg-white shadow-xl overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="sticky top-0 bg-white border-b border-slate-200 px-5 py-4 flex items-start justify-between">
          <div><h2 className="font-semibold text-slate-900">{user.full_name || user.email}</h2><p className="text-xs text-slate-500">{user.email} · last 50 security events</p></div>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded-lg hover:bg-slate-100"><X size={18} /></button>
        </div>
        {error && <div className="p-5"><Banner>{error}</Banner></div>}
        {!events && !error && <Spinner />}
        {events && events.length === 0 && <Empty>No security events for this account.</Empty>}
        <ul className="divide-y divide-slate-100">
          {(events || []).map(e => (
            <li key={e.id} className="px-5 py-3 text-sm">
              <div className="flex items-center gap-2"><Chip tone={eventTone(e.event)}>{e.label}</Chip><span className="text-xs text-slate-400 ml-auto" title={when(e.ts)}>{ago(e.ts)}</span></div>
              <div className="mt-1 text-xs text-slate-500">{[e.ip, e.location, device(e.user_agent)].filter(Boolean).join(' · ')}</div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function Duplicates({ notify, confirm, onChanged }) {
  const [groups, setGroups] = useState(null);
  const [selected, setSelected] = useState({});
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setError('');
    try {
      const data = await adminGet('/admin/duplicates');
      setGroups(data);
      setSelected(Object.fromEntries(data.map(g => [g.key, g.accounts.filter(a => !a.original && !a.suspended && !a.role).map(a => a.id)])));
    } catch (err) { setError(message(err, 'Could not load duplicate accounts.')); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = (key, id) => setSelected(s => ({ ...s, [key]: s[key].includes(id) ? s[key].filter(x => x !== id) : [...s[key], id] }));
  const act = (group, action) => {
    const ids = selected[group.key] || [];
    const emails = group.accounts.filter(a => ids.includes(a.id)).map(a => a.email);
    confirm({
      title: action === 'delete' ? `Delete ${ids.length} duplicate account(s)?` : `Suspend ${ids.length} duplicate account(s)?`,
      tone: 'red', confirmLabel: action === 'delete' ? 'Delete permanently' : 'Suspend',
      body: <><p>{emails.join(', ')}</p><p className="mt-2">{action === 'delete' ? 'Their data is removed and cannot be recovered.'
        : 'They are signed out and cannot sign in. You can restore them from the user list.'}</p></>,
      onConfirm: async () => { const r = await adminPost('/admin/duplicates/reject', { user_ids: ids, action }); notify(r.message); await load(); onChanged(); },
      errorText: (err) => message(err, 'Could not update these accounts.'),
    });
  };
  const dismiss = (group) => confirm({
    title: 'Mark as not duplicates?', confirmLabel: 'Not duplicates',
    body: 'These accounts belong to different people (for example colleagues on one office network). The group will not be shown again.',
    onConfirm: async () => { await adminPost('/admin/duplicates/dismiss', { key: group.key }); notify('Group dismissed'); await load(); onChanged(); },
    errorText: (err) => message(err, 'Could not dismiss this group.'),
  });

  if (error) return <Banner onClose={() => setError('')}>{error}</Banner>;
  if (!groups) return <Spinner />;
  if (groups.length === 0) return <div className={card}><Empty>No suspected duplicate accounts. New sign-ups that reuse an address are refused automatically.</Empty></div>;
  return (
    <div className="space-y-4">
      <Banner tone="blue">Sign-ups that reuse an email address (including dot and +tag variants), disposable inboxes, and more than 5 accounts from one network
        in a day are refused automatically. The groups below are older accounts or looser matches for you to review. The oldest account is treated as the original.</Banner>
      {groups.map(g => (
        <div key={g.key} className={`${card} overflow-hidden`}>
          <div className="px-5 py-4 flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-0"><div className="font-semibold text-slate-900">{REASON[g.reason]}</div>
              <div className="text-xs text-slate-500 font-mono truncate">{g.value}</div></div>
            {g.active_duplicates === 0 ? <Chip tone="green">Resolved</Chip> : <Chip tone="amber">{g.active_duplicates} to review</Chip>}
          </div>
          <table className="w-full">
            <thead><tr><Th>{''}</Th><Th>Account</Th><Th>Joined</Th><Th>Last sign-in</Th><Th>Sign-up IP</Th><Th>Status</Th></tr></thead>
            <tbody>{g.accounts.map(a => (
              <tr key={a.id}>
                <Td className="w-10"><input type="checkbox" aria-label={`Select ${a.email}`} disabled={a.original || !!a.role}
                  checked={(selected[g.key] || []).includes(a.id)} onChange={() => toggle(g.key, a.id)} className="accent-rose-600" /></Td>
                <Td><div className="font-medium">{a.full_name || '—'}</div><div className="text-xs text-slate-500">{a.email}</div></Td>
                <Td className="text-slate-500">{a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}</Td>
                <Td className="text-slate-500">{ago(a.last_login_at)}</Td>
                <Td className="font-mono text-xs">{a.signup_ip || '—'}</Td>
                <Td className="space-x-1">{a.original && <Chip tone="green">Original</Chip>}{a.suspended && <Chip tone="red">Suspended</Chip>}
                  {a.role && <Chip tone="violet">Admin</Chip>}{!a.is_verified && <Chip>Unverified</Chip>}</Td>
              </tr>))}
            </tbody>
          </table>
          <div className="px-5 py-3 border-t border-slate-100 flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => dismiss(g)}>Not duplicates</Button>
            <Button size="sm" variant="danger" icon={PauseCircle} disabled={!(selected[g.key] || []).length} onClick={() => act(g, 'suspend')}>Reject (suspend)</Button>
            <Button size="sm" icon={Trash2} disabled={!(selected[g.key] || []).length} onClick={() => act(g, 'delete')}>Delete</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function UsersTab({ notify, confirm, focus, duplicateCount, onChanged }) {
  const [view, setView] = useState(focus === 'duplicates' ? 'duplicates' : 'all');
  const [filters, setFilters] = useState({ q: '', role: '', status: '' });
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [activity, setActivity] = useState(null);
  const [exporting, setExporting] = useState(false);

  const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
  const load = useCallback(async () => {
    setError('');
    try { setData(await adminGet('/admin/accounts', { ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), page, page_size: 25 })); }
    catch (err) { setError(message(err, 'Could not load users.')); }
  }, [filters, page]);
  useEffect(() => { if (view === 'all') load(); }, [view, load]);

  const run = (opts) => confirm({ ...opts, errorText: (err) => message(err, 'Could not complete this action.'),
    onConfirm: async (reason) => { const r = await opts.call(reason); notify(r.message || 'Done'); await load(); onChanged(); } });
  const actions = (u) => [
    { label: 'View security activity', icon: Activity, onClick: () => setActivity(u) },
    { label: 'Sign out everywhere', icon: LogOut, onClick: () => run({ title: `Sign ${u.email} out everywhere?`, confirmLabel: 'Sign out',
      body: 'Every session on every device ends immediately. They can sign in again.', call: () => adminPost(`/admin/users/${u.id}/sign-out`) }) },
    { label: 'Force password reset', icon: KeyRound, onClick: () => run({ title: `Force ${u.email} to reset their password?`, confirmLabel: 'Force reset',
      body: 'They are signed out and cannot sign in until they set a new password with the link we email them.', call: () => adminPost(`/admin/users/${u.id}/force-password-reset`) }) },
    u.role === 'candidate' && { label: 'Make employer', icon: Briefcase, onClick: () => run({ title: `Make ${u.email} an employer?`, confirmLabel: 'Make employer',
      body: 'They will be able to post jobs and review applicants.', call: () => adminPatch(`/admin/users/${u.id}/make-hr`) }) },
    u.status === 'suspended'
      ? { label: 'Restore account', icon: PlayCircle, onClick: () => run({ title: `Restore ${u.email}?`, confirmLabel: 'Restore', call: () => adminPost(`/admin/users/${u.id}/unsuspend`) }) }
      : { label: 'Suspend account', icon: PauseCircle, tone: 'amber', onClick: () => run({ title: `Suspend ${u.email}?`, tone: 'red', confirmLabel: 'Suspend',
        body: 'They are signed out everywhere and cannot sign in until restored.', reasonLabel: 'Reason (kept in the audit log)',
        call: (reason) => adminPost(`/admin/users/${u.id}/suspend`, { reason }) }) },
    { label: 'Delete account…', icon: Trash2, tone: 'red', divider: true, onClick: () => run({ title: `Delete ${u.email}?`, tone: 'red', confirmLabel: 'Delete permanently',
      body: 'The account and its data are removed and cannot be recovered. Consider suspending instead.', call: () => adminDelete(`/admin/users/${u.id}`) }) },
  ];

  const exportCsv = async () => {
    setExporting(true);
    try { await downloadCsv('/admin/accounts.csv', params, 'users.csv'); }
    catch (err) { setError(message(err, 'Could not export users.')); }
    finally { setExporting(false); }
  };
  const setFilter = (change) => { setPage(1); setFilters(f => ({ ...f, ...change })); };

  return (
    <div className="space-y-4">
      <Segmented size="md" value={view} onChange={setView}
        options={[['all', 'All users'], ['duplicates', `Duplicate accounts${duplicateCount ? ` (${duplicateCount})` : ''}`]]} />
      {view === 'duplicates' ? <Duplicates notify={notify} confirm={confirm} onChanged={onChanged} /> : (
        <div className={`${card} overflow-hidden`}>
          <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <SearchInput value={query} onChange={setQuery} onSubmit={() => setFilter({ q: query.trim() })} placeholder="Search name, email or company" width="w-72" />
              <Select label="Role" value={filters.role} onChange={role => setFilter({ role })}
                options={[['', 'All roles'], ['candidate', 'Candidates'], ['employer', 'Employers'], ['admin', 'Admins']]} />
              <Select label="Status" value={filters.status} onChange={status => setFilter({ status })}
                options={[['', 'Any status'], ['active', 'Active'], ['suspended', 'Suspended'], ['unverified', 'Unverified'],
                  ['awaiting_approval', 'Awaiting approval'], ['no_2fa', 'Without two-step verification']]} />
            </div>
            <Button icon={Download} busy={exporting} onClick={exportCsv}>Export CSV</Button>
          </div>
          {error && <div className="px-5 pb-3"><Banner onClose={() => setError('')}>{error}</Banner></div>}
          {!data && !error ? <Spinner /> : data && (
            <>
              <div className="overflow-x-auto"><table className="w-full">
                <thead><tr><Th>User</Th><Th>Role</Th><Th>Plan</Th><Th>Status</Th><Th>Last sign-in</Th><Th>Joined</Th><Th right>Actions</Th></tr></thead>
                <tbody>{data.items.map(u => {
                  const [roleLabel, roleTone] = ROLE[u.role] || [u.role, 'slate'];
                  const [statusLabel, statusTone] = STATUS[u.status] || [u.status, 'slate'];
                  return (
                    <tr key={u.id} className={u.status === 'suspended' ? 'bg-rose-50/40' : 'hover:bg-slate-50/60'}>
                      <Td><div className="flex items-center gap-3">
                        <div className="w-8 h-8 shrink-0 rounded-full bg-emerald-100 text-emerald-700 grid place-items-center text-xs font-semibold">{initials(u.full_name, u.email)}</div>
                        <div className="min-w-0"><div className="font-medium truncate">{u.full_name || '—'}</div>
                          <div className="text-xs text-slate-500 truncate">{u.email}{u.company_name ? ` · ${u.company_name}` : ''}</div></div>
                      </div></Td>
                      <Td><Chip tone={roleTone}>{roleLabel}</Chip></Td>
                      <Td>{u.plan_lifetime
                        ? <Chip tone="violet" title="Enterprise for life: unlimited, never billed">Enterprise · Lifetime</Chip>
                        : <span className="capitalize">{u.plan || '—'}</span>}</Td>
                      <Td><div className="flex flex-wrap gap-1"><Chip tone={statusTone} title={u.suspended_reason || ''}>{statusLabel}</Chip>
                        {u.mfa_enabled && <Chip tone="green">2FA</Chip>}{u.force_password_reset && <Chip tone="amber">Reset required</Chip>}</div></Td>
                      <Td className="text-slate-600 whitespace-nowrap" title={u.last_login_ip || ''}>{u.last_login_at ? <>{ago(u.last_login_at)}{u.last_login_location ? ` · ${u.last_login_location}` : ''}</> : 'Never'}</Td>
                      <Td className="text-slate-500 whitespace-nowrap">{u.created_at ? new Date(u.created_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' }) : '—'}</Td>
                      <Td className="text-right"><Menu label={`Actions for ${u.email}`} items={actions(u)} /></Td>
                    </tr>);
                })}</tbody>
              </table></div>
              {data.items.length === 0 && <Empty>No users match these filters.</Empty>}
              <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
        </div>
      )}
      {activity && <ActivityDrawer user={activity} onClose={() => setActivity(null)} />}
      {data && view === 'all' && <p className="text-xs text-slate-500">{num(data.total)} account(s) match.</p>}
    </div>
  );
}
