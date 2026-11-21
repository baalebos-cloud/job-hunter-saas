import { useState } from 'react';
import axios from 'axios';
import { errorText } from '../../lib/session';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Second sign-in step for accounts with two-step verification.
export default function MfaChallenge({ mfaToken, onSuccess, onCancel, accent = 'emerald' }) {
  const [code, setCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const button = accent === 'blue' ? 'bg-blue-600 hover:bg-blue-500' : 'bg-emerald-600 hover:bg-emerald-500';

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const { data } = await axios.post(`${API_BASE_URL}/auth/login/mfa`, { mfa_token: mfaToken, code: code.trim() },
        { withCredentials: true });
      onSuccess(data);
    } catch (err) {
      setError(errorText(err, 'That code is not valid.'));
      if (err?.response?.status === 401 && /expired/i.test(err?.response?.data?.detail || '')) setTimeout(onCancel, 1500);
    } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="space-y-5" aria-labelledby="mfa-title">
      <div>
        <h2 id="mfa-title" className="text-xl font-black text-white">Two-step verification</h2>
        <p className="text-slate-400 text-sm mt-1">
          {useRecovery ? 'Enter one of the recovery codes you saved when you turned on two-step verification.'
            : 'Open your authenticator app and enter the 6-digit code for Baalebos Cloud.'}
        </p>
      </div>
      {error && <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-2xl text-sm font-bold">{error}</div>}
      <input value={code} onChange={e => setCode(e.target.value)} required autoFocus aria-label={useRecovery ? 'Recovery code' : '6-digit code'}
        inputMode={useRecovery ? 'text' : 'numeric'} autoComplete="one-time-code" maxLength={useRecovery ? 32 : 6}
        placeholder={useRecovery ? 'xxxx-xxxx-xxxx' : '123456'}
        className="w-full px-4 py-4 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-emerald-500 text-white font-mono text-lg tracking-[0.3em] text-center placeholder:text-slate-600" />
      <button type="submit" disabled={busy}
        className={`w-full ${button} text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest disabled:bg-slate-700 disabled:text-slate-500`}>
        {busy ? 'Checking…' : 'Verify and sign in'}
      </button>
      <div className="flex justify-between text-xs font-bold">
        <button type="button" onClick={() => { setUseRecovery(r => !r); setCode(''); setError(''); }} className="text-slate-400 hover:text-white">
          {useRecovery ? 'Use authenticator code' : 'Use a recovery code'}
        </button>
        <button type="button" onClick={onCancel} className="text-slate-500 hover:text-white">Back to sign in</button>
      </div>
    </form>
  );
}
