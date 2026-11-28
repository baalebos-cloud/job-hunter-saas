import { useState } from 'react';
import axios from 'axios';
import { errorText } from '../../lib/session';
import { buttonCls } from './authStyles';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Second sign-in step for accounts with two-step verification.
export default function MfaChallenge({ mfaToken, onSuccess, onCancel }) {
  const [code, setCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
    <form onSubmit={submit} className="space-y-5" aria-label="Two-step verification">
      <p className="text-[15px] text-slate-600">
        {useRecovery ? 'Enter one of the recovery codes you saved when you turned on two-step verification.'
          : 'Open your authenticator app and enter the 6-digit code for Baalebos.'}
      </p>
      {error && <div role="alert" className="rounded-[10px] border border-rose-200 bg-rose-50 px-4 py-3 text-[14px] text-rose-800">{error}</div>}
      <input value={code} onChange={e => setCode(e.target.value)} required autoFocus aria-label={useRecovery ? 'Recovery code' : '6-digit code'}
        inputMode={useRecovery ? 'text' : 'numeric'} autoComplete="one-time-code" maxLength={useRecovery ? 32 : 6}
        placeholder={useRecovery ? 'xxxx-xxxx-xxxx' : '123456'}
        className="w-full rounded-[10px] border border-[#d6d3cc] bg-white px-4 py-3.5 text-center font-mono text-xl tracking-[0.3em] text-[#0b1324] placeholder:text-[#c4c0b7] outline-none focus:border-[#0b1324] focus:ring-2 focus:ring-[#0b1324]/10" />
      <button type="submit" disabled={busy} className={buttonCls}>{busy ? 'Checking…' : 'Verify and sign in'}</button>
      <div className="flex justify-between text-[13.5px] font-semibold">
        <button type="button" onClick={() => { setUseRecovery(r => !r); setCode(''); setError(''); }} className="text-emerald-700 hover:text-emerald-800">
          {useRecovery ? 'Use authenticator code' : 'Use a recovery code'}
        </button>
        <button type="button" onClick={onCancel} className="text-slate-600 hover:text-slate-900">Back to sign in</button>
      </div>
    </form>
  );
}
