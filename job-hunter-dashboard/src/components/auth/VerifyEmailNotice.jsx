import { useState } from 'react';
import axios from 'axios';
import { errorText } from '../../lib/session';
import { buttonCls } from './authStyles';

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
    <div className="rounded-md border border-[#e2ddd2] bg-white p-6 text-[15px]" role="status">
      <h2 className="text-[19px] font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 leading-relaxed text-slate-600">
        {intro || 'We sent a verification link to'} <strong className="font-semibold text-[#0b1324] [overflow-wrap:anywhere]">{email}</strong>.
        {' '}Open it to activate your account, then sign in. Check your spam folder if you don&apos;t see it within a few minutes.
      </p>
      {note && <p className={`mt-3 text-[14px] font-medium ${state === 'error' ? 'text-rose-700' : 'text-emerald-700'}`}>{note}</p>}
      <div className="mt-5 space-y-3">
        <button type="button" onClick={resend} disabled={state === 'sending' || state === 'sent'} className={buttonCls}>
          {state === 'sending' ? 'Sending…' : state === 'sent' ? 'Link sent' : 'Resend verification email'}
        </button>
        {onBack
          ? <button type="button" onClick={onBack} className="w-full text-[14px] font-semibold text-slate-600 hover:text-slate-900">Back to sign in</button>
          : <a href="/login" className="block text-center text-[14px] font-semibold text-slate-600 hover:text-slate-900">Go to sign in</a>}
      </div>
    </div>
  );
}
