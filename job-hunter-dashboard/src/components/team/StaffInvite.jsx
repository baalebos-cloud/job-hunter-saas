import { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Loader2, ShieldCheck, XCircle } from 'lucide-react';
import { errorText, signOut } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const KEY = 'staffInvite';
const store = {
  get: () => { try { return localStorage.getItem(KEY); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(KEY, v); } catch { /* storage blocked */ } },
  clear: () => { try { localStorage.removeItem(KEY); } catch { /* storage blocked */ } },
};

// /staff-invite?token=…  The invited person reviews a staff role and accepts or declines it.
export default function StaffInvite() {
  const token = new URLSearchParams(window.location.search).get('token') || store.get();
  const signedIn = !!localStorage.getItem('token');
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState('');
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState('');
  const [done, setDone] = useState(null);     // { kind: 'accepted' | 'declined', twoStep }

  useEffect(() => {
    if (!token) { setError('This page needs the link from your invitation email.'); return; }
    store.set(token);
    axios.get(`${API}/staff-invites/${encodeURIComponent(token)}`)
      .then(r => setInvite(r.data))
      .catch(err => { store.clear(); setError(errorText(err, 'This invitation could not be loaded.')); });
  }, [token]);

  const accept = async () => {
    setBusy('accept'); setError('');
    try {
      const r = await axios.post(`${API}/staff-invites/accept`, { token, confidentiality: agree },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      store.clear(); setDone({ kind: 'accepted', twoStep: r.data.two_step_required });
    } catch (err) { setError(errorText(err, 'The invitation could not be accepted. Please retry.')); }
    finally { setBusy(''); }
  };
  const decline = async () => {
    setBusy('decline'); setError('');
    try { await axios.post(`${API}/staff-invites/decline`, { token }); store.clear(); setDone({ kind: 'declined' }); }
    catch (err) { setError(errorText(err, 'The invitation could not be declined. Please retry.')); }
    finally { setBusy(''); }
  };

  const shell = (children) => (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-6" style={{ fontFamily: 'Inter, sans-serif' }}>
      <main className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl p-7 shadow-sm">
        <a href="/" className="text-lg font-bold">baalebos<span className="text-emerald-600">.</span></a>
        <div className="mt-6">{children}</div>
      </main>
    </div>);

  if (done?.kind === 'accepted') return shell(<div role="status">
    <CheckCircle2 className="text-emerald-600" size={36} />
    <h1 className="mt-3 text-xl font-semibold">You are now {invite?.label}</h1>
    <p className="mt-2 text-sm text-slate-600">For your security you were signed out on every device. Sign in again to open {invite?.place}.
      {done.twoStep && ' You will be asked to turn on two-step verification first: keep an authenticator app ready.'}</p>
    <button type="button" onClick={() => signOut(axios)} className="mt-5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold px-4 py-2.5">Sign in again</button>
  </div>);
  if (done?.kind === 'declined') return shell(<div role="status">
    <XCircle className="text-slate-500" size={36} />
    <h1 className="mt-3 text-xl font-semibold">Invitation declined</h1>
    <p className="mt-2 text-sm text-slate-600">Nothing changed on your account. If you declined by mistake, ask the Baalebos owner to send a new invitation.</p>
  </div>);
  if (!invite) return shell(error ? <p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p>
    : <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>);

  return shell(<>
    <p className="text-sm text-slate-500">Invited by {invite.invited_by} · expires {new Date(invite.expires_at).toLocaleDateString()}</p>
    <h1 className="mt-1 text-2xl font-semibold">Join Baalebos as {invite.label}</h1>
    <p className="mt-2 text-slate-600">{invite.summary}</p>
    <h2 className="mt-5 text-sm font-semibold">What you will be able to do</h2>
    <ul className="mt-2 space-y-1.5 text-sm text-slate-700 list-disc pl-5">{invite.can.map(c => <li key={c}>{c}</li>)}</ul>
    <p className="mt-5 flex gap-2 text-xs text-slate-500"><ShieldCheck size={15} className="shrink-0" />Staff pages open only after two-step verification is on. Every action is recorded in the audit log.</p>
    {error && <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {!signedIn ? (
      <div className="mt-6 space-y-3">
        <p className="text-sm text-slate-700">This invitation is for <b>{invite.invited_email}</b>. Sign in to that account to accept it.</p>
        <a href="/login" className="inline-block rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold px-4 py-2.5">Sign in to accept</a>
        <button type="button" onClick={decline} disabled={!!busy} className="ml-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Decline</button>
      </div>
    ) : (
      <div className="mt-6 space-y-4">
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} className="mt-0.5 accent-emerald-600" />
          I will keep the personal data I see in this role confidential and use it only for my work at Baalebos.
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={accept} disabled={!agree || !!busy}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5">
            {busy === 'accept' && <Loader2 size={15} className="animate-spin" />}Accept the role</button>
          <button type="button" onClick={decline} disabled={!!busy} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Decline</button>
        </div>
      </div>
    )}
  </>);
}
