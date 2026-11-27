/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useCallback, useEffect, useState } from 'react';
import { Clock, KeyRound, MailCheck, RotateCw, ShieldCheck, UserCog, X } from 'lucide-react';
import { adminGet, ago, message } from '../adminApi';
import axios from 'axios';
import { Banner, Button, Chip, SearchInput, SectionHeader, Spinner, card } from '../ui';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const LABELS = {
  super_admin: 'Super admin', product_manager: 'Product manager', social_media_manager: 'Social media manager', legal_counsel: 'Legal counsel',
  security_auditor: 'Security auditor', engineering_lead: 'Engineering lead', compliance_officer: 'Compliance officer', viewer: 'Viewer',
};
const label = (role) => LABELS[role] || role;

// Owner console -> Access control (users:manage_roles): see the person's profile, then assign a role.
export default function AccessTab({ notify, confirm }) {
  const [matrix, setMatrix] = useState(null);
  const [q, setQ] = useState('');
  const [people, setPeople] = useState(null);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState({});
  const [invites, setInvites] = useState([]);
  const loadInvites = useCallback(() => adminGet('/rbac/invitations').then(setInvites).catch(() => {}), []);
  useEffect(() => { loadInvites(); }, [loadInvites]);
  const pendingFor = (id) => invites.find(i => i.user_id === id);

  const search = useCallback(async (query) => {
    try { setPeople(await adminGet('/rbac/users', { q: query || undefined })); setError(''); }
    catch (err) { setError(message(err, 'People could not be loaded.')); }
  }, []);
  useEffect(() => {
    adminGet('/rbac/matrix').then(setMatrix).catch(err => setError(message(err, 'Roles could not be loaded.')));
    search('');
  }, [search]);

  const assign = (person) => {
    const role = draft[person.id] ?? person.role ?? '';
    confirm({
      title: role ? `Invite ${person.full_name || person.email} to be a ${label(role)}?` : `Remove ${person.email}'s role?`,
      body: role ? `${matrix.roles[role]?.description || ''}. We email them an invitation with an overview of the role. Nothing changes until they accept, signed in to this account (the link expires in 7 days). Staff pages then open only after two-step verification is on.`
        : 'They lose console access straight away and are signed out everywhere. We email them to let them know.',
      confirmLabel: role ? 'Send invitation' : 'Remove role',
      tone: role ? undefined : 'red',
      errorText: (err) => message(err, 'The role could not be changed.'),
      onConfirm: async () => {
        await axios.put(`${API}/rbac/users/${person.id}/role`, { role: role || null }, { headers: headers() });
        notify(role ? `Invitation sent to ${person.email}. The ${label(role)} role starts when they accept.`
          : `${person.email} no longer has a staff role. We emailed them.`);
        setDraft(d => ({ ...d, [person.id]: undefined })); search(q); loadInvites();
      },
    });
  };

  const resend = async (i) => {
    try { await axios.post(`${API}/rbac/invitations/${i.id}/resend`, {}, { headers: headers() }); notify(`A new invitation link was sent to ${i.email}.`); loadInvites(); }
    catch (err) { setError(message(err, 'The invitation could not be resent.')); }
  };
  const cancel = (i) => confirm({
    title: `Cancel the invitation for ${i.email}?`, body: 'The link stops working straight away. You can invite them again later.',
    confirmLabel: 'Cancel invitation', tone: 'red', errorText: (err) => message(err, 'The invitation could not be cancelled.'),
    onConfirm: async () => { await axios.delete(`${API}/rbac/invitations/${i.id}`, { headers: headers() }); notify(`Invitation for ${i.email} cancelled.`); loadInvites(); },
  });

  if (!matrix) return error ? <Banner>{error}</Banner> : <Spinner />;
  const roles = Object.keys(matrix.roles);
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-start">
      <section className={`${card} xl:col-span-2 overflow-hidden`}>
        <SectionHeader title="Access control" subtitle={q ? 'Search results' : 'People with a staff role. Search by email to add someone.'}>
          <SearchInput value={q} onChange={setQ} onSubmit={() => search(q.trim())} placeholder="Search by email" />
        </SectionHeader>
        {error && <div className="px-5 pb-3"><Banner>{error}</Banner></div>}
        {!people ? <Spinner /> : (
          <ul className="divide-y divide-slate-100 border-t border-slate-100">
            {people.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">No one found. They must sign up and verify their email first.</li>}
            {people.map(p => {
              const value = draft[p.id] ?? p.role ?? '';
              const changed = value !== (p.role ?? '');
              return (
                <li key={p.id} className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-900">{p.full_name || p.email.split('@')[0]}</span>
                      {p.role && <Chip tone="violet">{label(p.role)}</Chip>}
                      {pendingFor(p.id) && <Chip tone="amber"><Clock size={11} />Invited: {label(pendingFor(p.id).role)}</Chip>}
                      {p.is_employer && <Chip tone="blue">Employer</Chip>}
                    </div>
                    <div className="text-xs text-slate-500 truncate">{p.email}{p.career_track ? ` · ${p.career_track}` : ''}</div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <Chip tone={p.is_verified ? 'green' : 'amber'}><MailCheck size={11} />{p.is_verified ? 'Email verified' : 'Email not verified'}</Chip>
                      <Chip tone={p.two_step ? 'green' : 'amber'}><KeyRound size={11} />{p.two_step ? 'Two-step on' : 'Two-step off'}</Chip>
                      {p.joined && <Chip>Joined {ago(p.joined)}</Chip>}
                      {p.last_login && <Chip>Last sign-in {ago(p.last_login)}</Chip>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select aria-label={`Role for ${p.email}`} value={value} disabled={!p.is_verified}
                      onChange={e => setDraft(d => ({ ...d, [p.id]: e.target.value }))}
                      className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white disabled:bg-slate-50">
                      <option value="">No staff role</option>
                      {roles.map(r => <option key={r} value={r}>{label(r)}</option>)}
                    </select>
                    <Button variant="primary" size="sm" disabled={!changed} onClick={() => assign(p)}>{value ? 'Invite' : 'Save'}</Button>
                  </div>
                </li>);
            })}
          </ul>)}
        {invites.length > 0 && (
          <div className="border-t border-slate-100 px-5 py-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Pending invitations</h3>
            <ul className="space-y-2 text-sm">
              {invites.map(i => (
                <li key={i.id} className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-900">{i.full_name || i.email}</span>
                  <Chip tone="violet">{label(i.role)}</Chip>
                  <span className={`text-xs ${i.status === 'expired' ? 'text-rose-700' : 'text-slate-500'}`}>
                    {i.status === 'expired' ? 'Expired unanswered' : `Expires ${new Date(i.expires_at).toLocaleDateString()}`}</span>
                  <span className="ml-auto flex gap-1">
                    <Button size="sm" icon={RotateCw} onClick={() => resend(i)}>Resend</Button>
                    <Button size="sm" icon={X} onClick={() => cancel(i)}>Cancel</Button>
                  </span>
                </li>))}
            </ul>
          </div>)}
      </section>
      <aside className={`${card} p-5 space-y-3`} aria-label="Roles">
        <h3 className="font-semibold text-slate-900 flex items-center gap-2"><UserCog size={16} />Roles</h3>
        <ul className="space-y-3 text-sm">
          {['product_manager', 'social_media_manager', 'legal_counsel', ...roles.filter(r => !['product_manager', 'social_media_manager', 'legal_counsel'].includes(r))]
            .filter(r => matrix.roles[r]).map(r => (
              <li key={r}><div className="font-medium text-slate-900">{label(r)}</div><div className="text-xs text-slate-500">{matrix.roles[r].description}</div></li>))}
        </ul>
        <p className="text-xs text-slate-500 flex gap-1.5"><ShieldCheck size={14} className="shrink-0" />A role starts only when the person accepts the emailed invitation. Staff must also turn on two-step verification before the console opens for them.</p>
      </aside>
    </div>
  );
}
