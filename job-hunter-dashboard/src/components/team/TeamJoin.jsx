import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle2, Loader2, Users } from 'lucide-react';
import { errorText } from '../../lib/session';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
export const INVITE_KEY = 'teamInvite';

function storedToken() {
  try { return localStorage.getItem(INVITE_KEY); } catch { return null; }
}
function forget() {
  try { localStorage.removeItem(INVITE_KEY); } catch { /* ignore */ }
}

// /team/join?token=… — open from the invite email. The token is kept until the
// person has signed in (or signed up and verified), then they accept here.
export default function TeamJoin() {
  const navigate = useNavigate();
  const signedIn = !!localStorage.getItem('token');
  const [token] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('token');
    if (fromUrl) {
      try { localStorage.setItem(INVITE_KEY, fromUrl); } catch { /* ignore */ }
      window.history.replaceState({}, '', '/team/join');      // keep the token out of history
    }
    return fromUrl || storedToken();
  });
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(null);

  useEffect(() => {
    if (!signedIn || !token) return;
    axios.get(`${API}/team/invite`, { params: { token }, headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
      .then(r => setInvite(r.data))
      .catch(err => { setError(errorText(err, 'This invite could not be opened.')); if ([404, 410].includes(err?.response?.status)) forget(); });
  }, [signedIn, token]);

  const accept = async () => {
    setBusy(true); setError('');
    try {
      const { data } = await axios.post(`${API}/team/accept`, { token }, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      forget(); setJoined(data.owner?.name || 'the team');
    } catch (err) { setError(errorText(err, 'The invite could not be accepted. Please retry.')); }
    finally { setBusy(false); }
  };
  const decline = () => { forget(); navigate('/'); };

  const card = 'max-w-md w-full bg-white border border-slate-200 rounded-2xl p-7 shadow-sm';
  const primary = 'inline-flex justify-center items-center gap-2 text-sm font-semibold rounded-xl px-5 py-2.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60';
  const secondary = 'inline-flex justify-center text-sm font-semibold rounded-xl px-5 py-2.5 border border-slate-200 bg-white text-slate-700 hover:bg-slate-50';

  let body;
  if (!token) {
    body = <p className="text-sm text-slate-600">This page needs the link from your invite email. Open the email and click <strong>Accept the invite</strong>.</p>;
  } else if (!signedIn) {
    body = (<>
      <p className="text-sm text-slate-600">Sign in with the email address the invite was sent to. New to Baalebos? Create an account with that address, verify it, then sign in. We&apos;ll bring you back here.</p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link to="/login" state={{ from: '/team/join' }} className={primary}>Sign in</Link>
        <Link to="/signup" className={secondary}>Create an account</Link>
      </div>
    </>);
  } else if (joined) {
    body = (<>
      <p className="flex items-center gap-2 text-sm text-emerald-800 bg-emerald-50 rounded-xl p-3"><CheckCircle2 size={18} />You joined {joined}&apos;s Enterprise team.</p>
      <p className="mt-3 text-sm text-slate-600">You now have Enterprise features. Your resumes stay private to you.</p>
      <div className="mt-5 flex gap-2"><Link to="/optimizer" className={primary}>Tailor a resume</Link><Link to="/settings" className={secondary}>View team</Link></div>
    </>);
  } else if (error) {
    body = (<>
      <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>
      <div className="mt-5"><Link to="/" className={secondary}>Go to dashboard</Link></div>
    </>);
  } else if (!invite) {
    body = <div className="py-6 flex justify-center"><Loader2 className="animate-spin text-emerald-600" /></div>;
  } else {
    body = (<>
      <p className="text-sm text-slate-600"><strong>{invite.owner.name}</strong> invited <strong>{invite.email}</strong> to their Enterprise team.</p>
      <ul className="mt-3 text-sm text-slate-600 list-disc pl-5 space-y-1">
        <li>Unlimited resume tailoring with priority processing</li>
        <li>Tailor one resume for up to 10 jobs at once</li>
        <li>Your resumes, applications and profile stay private to you</li>
      </ul>
      {!invite.email_matches && <p role="alert" className="mt-4 text-sm text-amber-800 bg-amber-50 rounded-xl p-3">
        You are signed in with a different email address. Sign in as {invite.email} to accept.</p>}
      <div className="mt-5 flex flex-wrap gap-2">
        <button type="button" onClick={accept} disabled={busy || !invite.email_matches} className={primary}>
          {busy && <Loader2 size={16} className="animate-spin" />}Join the team</button>
        <button type="button" onClick={decline} className={secondary}>Not now</button>
      </div>
    </>);
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className={card}>
        <span className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-700 grid place-items-center mb-4"><Users size={20} /></span>
        <h1 className="text-xl font-semibold text-slate-900 mb-2">Team invite</h1>
        {body}
      </div>
    </div>
  );
}
