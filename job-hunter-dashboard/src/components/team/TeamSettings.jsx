import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Mail, RefreshCw, Trash2, Users } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const day = iso => (iso ? new Date(iso).toLocaleDateString([], { dateStyle: 'medium' }) : '');

const BADGE = {
  active: 'bg-emerald-50 text-emerald-700',
  invited: 'bg-sky-50 text-sky-700',
  expired: 'bg-slate-100 text-slate-500',
};

// Settings → Team. Enterprise owners invite up to 9 people; members see their team.
export default function TeamSettings() {
  const [team, setTeam] = useState(null);
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');
  const [confirm, setConfirm] = useState(null);

  const load = useCallback(() => {
    axios.get(`${API}/team`, { headers: headers() })
      .then(r => setTeam(r.data)).catch(err => setError(errorText(err, 'Your team could not be loaded.')));
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (key, fn, success) => {
    setBusy(key); setError(''); setNotice('');
    try { await fn(); if (success) setNotice(success); setConfirm(null); load(); }
    catch (err) { setError(errorText(err, 'That did not work. Please retry.')); }
    finally { setBusy(''); }
  };

  const invite = (e) => {
    e.preventDefault();
    const address = email.trim();
    if (!address) return;
    act('invite', async () => { await axios.post(`${API}/team/invites`, { email: address }, { headers: headers() }); setEmail(''); },
      `Invite sent to ${address}. It expires in 7 days.`);
  };

  const shell = (children) => (
    <section id="team" className="bg-white border border-slate-200 rounded-3xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <Users size={18} className="text-emerald-600" />
        <h3 className="text-slate-900 font-black text-base">Team</h3>
      </div>
      {children}
      {notice && <p role="status" className="mt-3 text-sm text-emerald-800 bg-emerald-50 rounded-xl p-3">{notice}</p>}
      {error && <p role="alert" className="mt-3 text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
    </section>
  );

  if (!team) return shell(error ? null : <div className="py-6 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>);

  if (team.role === 'member') {
    return shell(<>
      <p className="text-sm text-slate-600 mt-2">
        You are on <strong>{team.owner?.name}</strong>&apos;s Enterprise team ({team.owner?.email}){team.joined_at ? ` since ${day(team.joined_at)}` : ''}.
        {team.active ? ' You have Enterprise features while their plan is active.' : ' Their Enterprise plan is not active right now, so you are on your own plan until it is renewed.'}
      </p>
      <p className="text-xs text-slate-500 mt-2">Your resumes, applications and profile are private to you. The team owner cannot see them.</p>
      {confirm === 'leave' ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-600">Leave the team? You will go back to your own plan.</span>
          <button type="button" disabled={!!busy} onClick={() => act('leave', () => axios.post(`${API}/team/leave`, {}, { headers: headers() }), 'You left the team.')}
            className="font-semibold rounded-xl px-4 py-2 border border-rose-200 text-rose-700 hover:bg-rose-50">Leave team</button>
          <button type="button" onClick={() => setConfirm(null)} className="font-semibold rounded-xl px-4 py-2 border border-slate-200">Cancel</button>
        </div>
      ) : (
        <button type="button" onClick={() => setConfirm('leave')} className="mt-4 text-sm font-semibold rounded-xl px-4 py-2 border border-slate-200 hover:bg-slate-50">Leave team</button>
      )}
    </>);
  }

  if (team.role === 'none') {
    return shell(<p className="text-sm text-slate-600 mt-2">
      Team access is part of Enterprise: invite up to 9 people, and each gets Enterprise features with their own private workspace.{' '}
      <a href="/pricing" className="font-semibold text-emerald-700 hover:underline">See plans</a></p>);
  }

  const full = team.seats_used >= team.seats_total;
  return shell(<>
    <p className="text-sm text-slate-600 mt-2">
      Invite up to {team.seats_total - 1} people. Each gets Enterprise features and their own private workspace; you cannot see their resumes.
    </p>
    <p className="text-sm font-semibold text-slate-800 mt-3">{team.seats_used} of {team.seats_total} seats used <span className="font-normal text-slate-500">(including you)</span></p>
    {!team.can_manage && <p className="mt-3 text-sm text-amber-800 bg-amber-50 rounded-xl p-3">
      Your Enterprise plan is not active, so your team is on their own plans until it is renewed. <a href="/pricing" className="font-semibold underline">Renew</a></p>}

    {team.can_manage && (
      <form onSubmit={invite} className="mt-4 flex flex-col sm:flex-row gap-2">
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="colleague@company.com" aria-label="Email to invite"
          disabled={full} className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm outline-none focus:border-emerald-500" />
        <button type="submit" disabled={full || busy === 'invite' || !email.trim()}
          className="inline-flex items-center justify-center gap-2 text-sm font-semibold rounded-xl px-4 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">
          {busy === 'invite' ? <Loader2 size={16} className="animate-spin" /> : <Mail size={16} />}Send invite</button>
      </form>)}
    {full && team.can_manage && <p className="mt-2 text-xs text-slate-500">Your team is full. Remove someone or cancel an invite to free a seat.</p>}

    {team.members.length > 0 && (
      <ul className="mt-5 divide-y divide-slate-100 border border-slate-100 rounded-2xl">
        {team.members.map(m => (
          <li key={m.id} className="p-3 flex flex-col sm:flex-row sm:items-center gap-2">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-slate-900 truncate">{m.name || m.email}</div>
              <div className="text-xs text-slate-500 truncate">
                {m.name ? `${m.email} · ` : ''}
                {m.status === 'active' ? `Joined ${day(m.accepted_at)}` : m.status === 'invited' ? `Invite expires ${day(m.expires_at)}` : 'Invite expired'}
              </div>
            </div>
            <span className={`self-start sm:self-auto text-[11px] font-semibold px-2 py-0.5 rounded-full capitalize ${BADGE[m.status]}`}>{m.status}</span>
            {confirm === m.id ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-600">{m.status === 'active' ? 'Remove from team?' : 'Cancel invite?'}</span>
                <button type="button" disabled={!!busy} onClick={() => act(`rm${m.id}`, () => axios.delete(`${API}/team/members/${m.id}`, { headers: headers() }),
                  m.status === 'active' ? `${m.email} was removed from your team.` : 'Invite cancelled.')}
                  className="font-semibold rounded-lg px-2.5 py-1.5 border border-rose-200 text-rose-700">Yes</button>
                <button type="button" onClick={() => setConfirm(null)} className="font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200">No</button>
              </div>
            ) : (
              <div className="flex gap-2">
                {m.status !== 'active' && team.can_manage && (
                  <button type="button" disabled={!!busy} onClick={() => act(`re${m.id}`, () => axios.post(`${API}/team/invites/${m.id}/resend`, {}, { headers: headers() }), `New invite sent to ${m.email}.`)}
                    className="inline-flex items-center gap-1 text-xs font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 hover:bg-slate-50"><RefreshCw size={13} />Resend</button>)}
                <button type="button" onClick={() => setConfirm(m.id)} aria-label={`Remove ${m.email}`}
                  className="inline-flex items-center gap-1 text-xs font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 text-rose-700 hover:bg-rose-50"><Trash2 size={13} />{m.status === 'active' ? 'Remove' : 'Cancel'}</button>
              </div>)}
          </li>))}
      </ul>)}
  </>);
}
