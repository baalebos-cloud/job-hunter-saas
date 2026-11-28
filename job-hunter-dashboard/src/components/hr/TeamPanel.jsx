/* eslint-disable react/prop-types -- the project does not use the prop-types package */
// Employer portal "Team" tab: who works on the company's jobs and in which role.
// Admins invite, change roles and remove people; everyone else sees the team.
import { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2 } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const h = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

const ROLE_HELP = [
  ['Admin', 'Everything, including the team.'],
  ['Recruiter', 'All jobs and applicants; posts and edits jobs.'],
  ['Hiring manager', 'Their hiring-team jobs; can move applicants.'],
  ['Interviewer', 'Their hiring-team jobs; view only for now.'],
];

const card = 'bg-white rounded-2xl border border-slate-200';
const inputCls = 'w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10';
const selectCls = 'rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 outline-none focus:border-emerald-600';

function daysLeft(iso) {
  if (!iso) return null;
  const days = Math.ceil((Date.parse(iso) + 7 * 864e5 - Date.now()) / 864e5);
  return days > 0 ? days : null;
}

function StatusText({ m }) {
  if (m.status === 'active') return <span className="text-emerald-700">Active</span>;
  if (m.status === 'expired') return <span className="text-slate-500">Expired</span>;
  const left = daysLeft(m.invited_at);
  return <span className="text-amber-700">Invited{left ? ` · expires in ${left} day${left === 1 ? '' : 's'}` : ''}</span>;
}

export default function TeamPanel({ company, onNotice, onChange }) {
  const [team, setTeam] = useState(null);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('recruiter');
  const [sending, setSending] = useState(false);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');

  const load = async () => {
    try { setTeam((await axios.get(`${API}/hr/team`, { headers: h() })).data); }
    catch (err) { setError(errorText(err, 'The team could not be loaded. Please refresh the page.')); }
  };
  useEffect(() => { load(); }, []);

  const act = async (key, request, success) => {
    setBusy(key); setError('');
    try { await request(); if (success) onNotice({ type: 'success', text: success }); await load(); onChange?.(); }
    catch (err) { setError(errorText(err, 'That change could not be saved. Please try again.')); }
    finally { setBusy(null); }
  };

  const invite = async (e) => {
    e.preventDefault();
    setSending(true); setError('');
    try {
      await axios.post(`${API}/hr/team/invites`, { email: email.trim(), role }, { headers: h() });
      onNotice({ type: 'success', text: `Invitation sent to ${email.trim()}.` });
      setEmail(''); await load(); onChange?.();
    } catch (err) { setError(errorText(err, 'The invitation could not be sent. Please try again.')); }
    finally { setSending(false); }
  };

  if (!team) return (
    <div className={`${card} p-10 flex justify-center`}>
      {error ? <p role="alert" className="text-sm text-rose-700">{error}</p> : <Loader2 className="animate-spin text-slate-400" />}
    </div>
  );

  const manage = team.can_manage;
  return (
    <div className={`grid gap-6 items-start ${manage ? 'lg:grid-cols-[minmax(0,1fr)_22rem]' : ''}`}>
      <section className={card} aria-labelledby="team-title">
        <div className="p-6 border-b border-slate-100">
          <h3 id="team-title" className="font-semibold text-slate-900">{company ? `${company}’s team` : 'Your team'}</h3>
          <p className="text-sm text-slate-500 mt-0.5">Everyone here works on {company || 'your company'}’s jobs. Hiring managers and interviewers only see the jobs they’re on the hiring team for.</p>
        </div>
        {error && <p role="alert" className="mx-6 mt-4 rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-800">{error}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr><th className="px-6 py-3 font-medium">Person</th><th className="py-3 pr-4 font-medium">Role</th><th className="py-3 pr-6 font-medium">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {team.members.map(m => (
                <tr key={m.id}>
                  <td className="px-6 py-3 min-w-[13rem]">
                    <p className="font-medium text-slate-900">{m.name || '—'}{m.is_you && <span className="text-slate-400 font-normal"> (you)</span>}</p>
                    <p className="text-slate-500 break-all">{m.email}</p>
                  </td>
                  <td className="py-3 pr-4">
                    {manage ? (
                      <select aria-label={`Role for ${m.name || m.email}`} className={selectCls} value={m.role} disabled={busy !== null}
                        onChange={e => act(`role-${m.id}`, () => axios.patch(`${API}/hr/team/members/${m.id}`, { role: e.target.value }, { headers: h() }))}>
                        {team.roles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                    ) : <span className="text-slate-700">{m.role_label}</span>}
                  </td>
                  <td className="py-3 pr-6">
                    <p><StatusText m={m} /></p>
                    <p className="mt-0.5 space-x-3 empty:hidden">
                    {manage && m.status !== 'active' && (
                      <button type="button" disabled={busy !== null} className="text-slate-600 underline hover:text-slate-900 disabled:opacity-50"
                        onClick={() => act(`resend-${m.id}`, () => axios.post(`${API}/hr/team/invites/${m.id}/resend`, {}, { headers: h() }), `Invitation sent again to ${m.email}.`)}>Resend</button>
                    )}
                    {manage && !m.is_you && (
                      <button type="button" disabled={busy !== null} className="text-rose-700 hover:text-rose-800 disabled:opacity-50"
                        onClick={() => {
                          const verb = m.status === 'active' ? 'Remove' : 'Cancel the invitation for';
                          if (!window.confirm(`${verb} ${m.name || m.email}?${m.status === 'active' ? ' They lose access to your jobs and are signed out.' : ''}`)) return;
                          act(`remove-${m.id}`, () => axios.delete(`${API}/hr/team/members/${m.id}`, { headers: h() }),
                            m.status === 'active' ? `${m.name || m.email} was removed from the team.` : 'Invitation cancelled.');
                        }}>{m.status === 'active' ? 'Remove' : 'Cancel'}</button>
                    )}
                    </p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {manage && (
        <form onSubmit={invite} className={`${card} p-6`} aria-labelledby="invite-title">
          <h3 id="invite-title" className="font-semibold text-slate-900">Invite a teammate</h3>
          <label htmlFor="invite-email" className="block text-sm font-medium text-slate-700 mt-4 mb-1.5">Work email</label>
          <input id="invite-email" type="email" required className={inputCls} value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" autoComplete="off" />
          <label htmlFor="invite-role" className="block text-sm font-medium text-slate-700 mt-3 mb-1.5">Role</label>
          <select id="invite-role" className={`${inputCls} py-2.5`} value={role} onChange={e => setRole(e.target.value)}>
            {team.roles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <button type="submit" disabled={sending}
            className="mt-4 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-4 py-2.5 disabled:opacity-60">
            {sending && <Loader2 size={16} className="animate-spin" />}Send invitation
          </button>
          <dl className="mt-5 text-xs text-slate-600 space-y-2">
            {ROLE_HELP.map(([name, text]) => <div key={name}><dt className="font-semibold text-slate-800">{name}</dt><dd>{text}</dd></div>)}
          </dl>
          <p className="text-xs text-slate-500 mt-4">The link works once and expires in 7 days. Removing someone signs them out at once.</p>
        </form>
      )}
    </div>
  );
}
