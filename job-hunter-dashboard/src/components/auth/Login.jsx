import { useState, useEffect } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { startSession, errorText } from '../../lib/session';
import MfaChallenge from './MfaChallenge';
import VerifyEmailNotice from './VerifyEmailNotice';
import PasswordInput from './PasswordInput';
import AuthShell, { AsideEyebrow, ErrorNote, ExampleList, Spinner } from './AuthShell';
import { buttonCls, fieldCls, labelCls, linkCls, quietLinkCls } from './authStyles';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export default function Login() {
  const location = useLocation();
  const requestedPath = location.state?.from;
  const pendingInvite = (() => { try { return !!localStorage.getItem('teamInvite'); } catch { return false; } })();
  const staffInvite = (() => { try { return localStorage.getItem('staffInvite'); } catch { return null; } })();
  const destination = ['/admin', '/hr', '/optimizer', '/resumes', '/jobs', '/applications', '/profile', '/settings', '/referral', '/team/join'].includes(requestedPath)
    ? requestedPath : staffInvite ? `/staff-invite?token=${encodeURIComponent(staffInvite)}` : (pendingInvite ? '/team/join' : '/');
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mfaToken, setMfaToken] = useState(null);
  const [unverified, setUnverified] = useState('');

  useEffect(() => {
    if (localStorage.getItem('token')) window.location.href = destination;
  }, [destination]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/login`, form, { withCredentials: true });
      if (res.data.mfa_required) { setMfaToken(res.data.mfa_token); return; }
      const token = res.data.access_token || res.data.token || null;
      if (token?.trim()) { startSession(token); window.location.href = destination; }
      else setError('Login succeeded but no token received.');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail?.code === 'email_not_verified') { setUnverified(detail.email || form.email); return; }
      setError(errorText(err, 'Invalid email or password.'));
    } finally { setLoading(false); }
  };

  const aside = (
    <>
      <AsideEyebrow>Your workspace</AsideEyebrow>
      <p className="mt-4 text-[28px] leading-snug font-semibold tracking-tight">Your tailored resumes, match scores and applications are where you left them.</p>
      <ExampleList title="My resumes" rows={[
        [<><b className="font-semibold">DevOps Engineer</b> · Contoso</>, '86%'],
        [<><b className="font-semibold">Cloud Engineer</b> · Fabrikam</>, '79%'],
        [<><b className="font-semibold">Platform Engineer</b> · Litware</>, '64%', 'amber']]} />
    </>
  );

  return (
    <AuthShell title={mfaToken ? 'Two-step verification' : 'Sign in'} aside={aside}
      intro={unverified || mfaToken ? null : 'Pick up where you left off: your resumes, matches and applications.'}>
      {error && <ErrorNote>{error}</ErrorNote>}
      {unverified ? (
        <VerifyEmailNotice email={unverified} title="Verify your email to sign in"
          intro="Your account isn't active yet. We sent a verification link to"
          onBack={() => setUnverified('')} />
      ) : mfaToken ? (
        <MfaChallenge mfaToken={mfaToken} onCancel={() => setMfaToken(null)}
          onSuccess={(data) => { startSession(data.access_token); window.location.href = destination; }} />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className={labelCls} htmlFor="login-email">Email</label>
            <input id="login-email" type="email" required autoComplete="email" placeholder="you@example.com" className={fieldCls}
              value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <div className="flex items-baseline justify-between">
              <label className={labelCls} htmlFor="login-password">Password</label>
              <a href="/forgot-password" className="text-[13.5px] font-semibold text-emerald-700 hover:text-emerald-800">Forgot password?</a>
            </div>
            <PasswordInput id="login-password" required autoComplete="current-password" className={fieldCls}
              value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
          </div>
          <button type="submit" disabled={loading} className={buttonCls}>{loading ? <><Spinner />Signing in…</> : 'Sign in'}</button>
        </form>
      )}
      <p className="mt-6 text-[14.5px] text-slate-600">New to Baalebos? <a href="/signup" className={linkCls}>Create a free account</a></p>
      <div className="mt-10 border-t border-[#e7e3da] pt-5 text-[13.5px] text-slate-600">
        Hiring? <a href="/hr/login" className={quietLinkCls}>Sign in to the employer portal</a>
      </div>
    </AuthShell>
  );
}
