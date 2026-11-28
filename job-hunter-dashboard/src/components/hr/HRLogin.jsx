// =============================================================================
// job-hunter-dashboard/src/components/hr/HRLogin.jsx
// Dedicated HR login — company email only, clear error states
// =============================================================================
import { useState } from 'react';
import axios from 'axios';
import PasswordInput from '../auth/PasswordInput';
import { startSession, errorText } from '../../lib/session';
import MfaChallenge from '../auth/MfaChallenge';
import AuthShell, { AsideEyebrow, ExampleList, Spinner } from '../auth/AuthShell';
import { buttonCls, fieldCls, hintCls, labelCls, linkCls, quietLinkCls } from '../auth/authStyles';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const BLOCKED_DOMAINS = new Set([
  'gmail.com','yahoo.com','yahoo.co.uk','hotmail.com','outlook.com',
  'live.com','icloud.com','me.com','aol.com','protonmail.com','proton.me',
]);


export default function HRLogin() {
  const [form, setForm]     = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');
  const [mfaToken, setMfaToken] = useState(null);
  const [emailError, setEmailError] = useState('');
  const [resendState, setResendState] = useState({ sending: false, message: '' });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const resendVerification = async () => {
    setResendState({ sending: true, message: '' });
    try {
      const res = await axios.post(`${API_BASE_URL}/hr-auth/resend-verification`, { email: form.email });
      setResendState({ sending: false, message: res.data.message });
    } catch (err) {
      setResendState({ sending: false, message: errorText(err, 'Could not send a new link. Please try again.') });
    }
  };

  const handleEmailChange = (e) => {
    const val = e.target.value;
    set('email', val);
    if (val.includes('@')) {
      const domain = val.toLowerCase().split('@')[1] || '';
      setEmailError(BLOCKED_DOMAINS.has(domain)
        ? `Employer accounts use a company email; ${domain} addresses can't be used.`
        : '');
    } else {
      setEmailError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (emailError) return;
    setLoading(true); setError(''); setResendState({ sending: false, message: '' });
    try {
      const res = await axios.post(`${API_BASE_URL}/hr-auth/login`, {
        email:    form.email,
        password: form.password,
      }, { withCredentials: true });
      if (res.data.mfa_required) { setMfaToken(res.data.mfa_token); return; }
      const token = res.data.access_token;
      if (token) {
        startSession(token);
        window.location.href = res.data.redirect || '/hr';
      }
    } catch (err) {
      const detail = errorText(err, 'Login failed. Please try again.');
      setError(detail);
    } finally { setLoading(false); }
  };

  const aside = (
    <>
      <AsideEyebrow dark>Employer portal</AsideEyebrow>
      <p className="mt-4 text-[28px] leading-snug font-semibold tracking-tight">See every applicant’s resume and how closely it matches your job description.</p>
      <ExampleList dark title="Applicants · Platform Engineer" rows={[
        [<b key="a" className="font-semibold">A. Bello</b>, 'Job match 88%'],
        [<b key="c" className="font-semibold">C. Mensah</b>, 'Job match 81%'],
        [<b key="j" className="font-semibold">J. Okoro</b>, 'Job match 64%', 'amber']]} />
    </>
  );

  return (
    <AuthShell employer asideTone="ink" aside={aside} title={mfaToken ? 'Two-step verification' : 'Employer sign in'}
      intro={mfaToken ? null : 'Manage your job posts and review applicants.'}>
      {error && (
        <div role="alert" className="mb-6 rounded-[10px] border border-rose-200 bg-rose-50 px-4 py-3 text-[14px] text-rose-800">
          <p>{error}</p>
          {error.includes('not been verified') && (
            <div className="mt-2 text-[13.5px]">
              <p>Check your inbox and spam folder for the verification email we sent when you registered.</p>
              <button type="button" onClick={resendVerification} disabled={resendState.sending}
                className="mt-2 font-semibold underline underline-offset-4 disabled:opacity-60">
                {resendState.sending ? 'Sending…' : 'Send a new verification link'}
              </button>
              {resendState.message && <p className="mt-2 font-medium text-emerald-800">{resendState.message}</p>}
            </div>
          )}
          {error.includes('not registered as an HR') && (
            <p className="mt-2 text-[13.5px]">Need an employer account? <a href="/hr/signup" className="font-semibold underline underline-offset-4">Apply for one</a></p>
          )}
          {error.includes('awaiting') && (
            <p className="mt-2 text-[13.5px]">Your company is still being reviewed. We’ll email you as soon as a decision is made.</p>
          )}
        </div>
      )}

      {mfaToken ? (
        <MfaChallenge mfaToken={mfaToken} onCancel={() => setMfaToken(null)}
          onSuccess={(data) => { startSession(data.access_token); window.location.href = data.redirect || '/hr'; }} />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className={labelCls} htmlFor="hr-login-email">Work email</label>
            <input id="hr-login-email" type="email" required autoComplete="email" placeholder="you@yourcompany.com"
              className={`${fieldCls} ${emailError ? 'border-rose-400' : ''}`} aria-invalid={!!emailError}
              value={form.email} onChange={handleEmailChange} />
            {emailError ? <p className="mt-1.5 text-[12.5px] font-medium text-rose-700">{emailError}</p>
              : <p className={hintCls}>Use the company address you registered with.</p>}
          </div>
          <div>
            <div className="flex items-baseline justify-between">
              <label className={labelCls} htmlFor="hr-login-password">Password</label>
              <a href="/forgot-password" className="text-[13.5px] font-semibold text-emerald-700 hover:text-emerald-800">Forgot password?</a>
            </div>
            <PasswordInput id="hr-login-password" autoComplete="current-password" required className={fieldCls}
              value={form.password} onChange={e => set('password', e.target.value)} />
          </div>
          <button type="submit" disabled={loading || !!emailError} className={buttonCls}>{loading ? <><Spinner />Signing in…</> : 'Sign in'}</button>
        </form>
      )}
      <p className="mt-6 text-[14.5px] text-slate-600">No employer account yet? <a href="/hr/signup" className={linkCls}>Apply for one</a></p>
      <div className="mt-10 border-t border-[#e7e3da] pt-5 text-[13.5px] text-slate-600">
        Looking for a job? <a href="/login" className={quietLinkCls}>Candidate sign in</a>
      </div>
    </AuthShell>
  );
}
