import { useState } from 'react';
import axios from 'axios';
import { errorText } from '../../lib/session';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Shown after sign-up and when an unverified account tries to sign in.
// Accounts cannot sign in until the email address is verified.
export default function VerifyEmailNotice({ email, title = 'Check your inbox', intro, onBack }) {
  const [state, setState] = useState('idle');   // idle | sending | sent | error
  const [note, setNote] = useState('');

  const resend = async () => {
    setState('sending'); setNote('');
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/verification/resend`, { email });
      setState('sent'); setNote(res.data?.message || 'A new verification link is on its way.');
    } catch (err) {
      setState('error'); setNote(errorText(err, 'Could not send a new link. Please try again shortly.'));
    }
  };

  return (
    <div className="p-6 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl text-sm" role="status">
      <div className="text-3xl mb-3" aria-hidden="true">📬</div>
      <h2 className="text-lg font-black text-white mb-2">{title}</h2>
      <p className="text-slate-300 leading-relaxed">
        {intro || 'We sent a verification link to'} <strong className="text-white [overflow-wrap:anywhere]">{email}</strong>.
        {' '}Open it to activate your account, then sign in. Check your spam folder if you don&apos;t see it within a few minutes.
      </p>
      {note && <p className={`mt-3 font-semibold ${state === 'error' ? 'text-rose-400' : 'text-emerald-400'}`}>{note}</p>}
      <div className="mt-5 flex flex-wrap gap-3">
        <button type="button" onClick={resend} disabled={state === 'sending' || state === 'sent'}
          className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white font-black px-5 py-3 rounded-xl text-xs uppercase tracking-widest">
          {state === 'sending' ? 'Sending…' : state === 'sent' ? 'Link sent' : 'Resend verification email'}
        </button>
        {onBack
          ? <button type="button" onClick={onBack} className="text-slate-300 hover:text-white font-bold px-3 py-3 text-xs uppercase tracking-widest">Back to sign in</button>
          : <a href="/login" className="text-slate-300 hover:text-white font-bold px-3 py-3 text-xs uppercase tracking-widest">Go to sign in →</a>}
      </div>
    </div>
  );
}
