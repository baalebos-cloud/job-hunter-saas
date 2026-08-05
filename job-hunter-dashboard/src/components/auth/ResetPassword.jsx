// =============================================================================
// job-hunter-dashboard/src/components/auth/ResetPassword.jsx
// Reads ?token= from URL, submits new password to /auth/reset-password
// =============================================================================
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-emerald-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600';
const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2';

export default function ResetPassword() {
  const [token, setToken]       = useState('');
  const [form, setForm]         = useState({ password: '', confirm: '' });
  const [loading, setLoading]   = useState(false);
  const [success, setSuccess]   = useState(false);
  const [error, setError]       = useState('');
  const [strength, setStrength] = useState(0);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('token');
    if (!t) setError('Invalid reset link. Please request a new one.');
    else setToken(t);
  }, []);

  const checkStrength = (pwd) => {
    let score = 0;
    if (pwd.length >= 8)  score++;
    if (pwd.length >= 12) score++;
    if (/[A-Z]/.test(pwd)) score++;
    if (/[0-9]/.test(pwd)) score++;
    if (/[^A-Za-z0-9]/.test(pwd)) score++;
    setStrength(score);
  };

  const handlePasswordChange = (e) => {
    set('password', e.target.value);
    checkStrength(e.target.value);
  };

  const strengthLabel = ['', 'Weak', 'Fair', 'Good', 'Strong', 'Very Strong'][strength];
  const strengthColor = ['', 'bg-rose-500', 'bg-amber-500', 'bg-yellow-400', 'bg-emerald-400', 'bg-emerald-500'][strength];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (form.password !== form.confirm) { setError('Passwords do not match.'); return; }
    setLoading(true); setError('');
    try {
      await axios.post(`${API_BASE_URL}/auth/reset-password`, null, {
        params: { token, new_password: form.password }
      });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Reset failed. The link may have expired.');
    } finally { setLoading(false); }
  };

  if (success) return (
    <div className="app-canvas min-h-screen w-full flex items-center justify-center p-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />
      <div className="max-w-md w-full relative z-10 text-center">
        <div className="w-20 h-20 bg-emerald-500/10 border-2 border-emerald-500/30 rounded-full flex items-center justify-center mx-auto mb-6">
          <span className="text-4xl">🔓</span>
        </div>
        <h1 className="text-3xl font-black text-white mb-3"
          style={{ fontFamily: "'Playfair Display', serif" }}>Password updated!</h1>
        <p className="text-slate-400 text-base leading-relaxed mb-8">
          Your password has been reset successfully. You can now log in with your new password.
        </p>
        <a href="/login"
          className="block w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all shadow-xl shadow-emerald-600/20 text-center">
          Login Now →
        </a>
      </div>
    </div>
  );

  return (
    <div className="app-canvas min-h-screen w-full flex items-center justify-center p-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />
      <div className="w-full max-w-md relative z-10">

        {/* Logo */}
        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/30">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
          </div>
          <div>
            <div className="text-white font-black text-lg tracking-tight">BAALEBOS CLOUD</div>
            <div className="text-emerald-400 text-[10px] font-bold uppercase tracking-[0.2em]">AI Talent Infrastructure</div>
          </div>
        </div>

        <div className="mb-8">
          <h1 className="text-3xl font-black text-white mb-2"
            style={{ fontFamily: "'Playfair Display', serif" }}>Set new password</h1>
          <p className="text-slate-400 text-sm font-medium">
            Choose a strong password for your account.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl">
            <p className="text-rose-400 text-sm font-bold">⚠️ {error}</p>
            {error.includes('expired') && (
              <a href="/forgot-password"
                className="text-rose-300 text-xs font-black underline mt-1 inline-block">
                Request a new reset link →
              </a>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelCls}>New Password</label>
            <input type="password" required placeholder="Min. 8 characters"
              className={inputCls} value={form.password}
              onChange={handlePasswordChange} />
            {form.password && (
              <div className="mt-2">
                <div className="flex gap-1 mb-1">
                  {[1,2,3,4,5].map(i => (
                    <div key={i} className={`h-1 flex-1 rounded-full transition-all ${i <= strength ? strengthColor : 'bg-slate-800'}`} />
                  ))}
                </div>
                <p className={`text-xs font-bold ${strengthColor.replace('bg-','text-')}`}>
                  {strengthLabel}
                </p>
              </div>
            )}
          </div>

          <div>
            <label className={labelCls}>Confirm New Password</label>
            <input type="password" required placeholder="Re-enter your password"
              className={`${inputCls} ${form.confirm && form.confirm !== form.password ? 'border-rose-500' : form.confirm && form.confirm === form.password ? 'border-emerald-500' : ''}`}
              value={form.confirm} onChange={e => set('confirm', e.target.value)} />
            {form.confirm && form.confirm !== form.password && (
              <p className="text-rose-400 text-xs font-bold mt-1.5">❌ Passwords do not match</p>
            )}
            {form.confirm && form.confirm === form.password && (
              <p className="text-emerald-400 text-xs font-bold mt-1.5">✓ Passwords match</p>
            )}
          </div>

          <button type="submit" disabled={loading || !token}
            className="w-full bg-emerald-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-emerald-500 active:scale-[0.98] transition-all shadow-xl shadow-emerald-600/20 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed mt-2">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Updating...
              </span>
            ) : 'Update Password →'}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-slate-800 text-center">
          <a href="/login" className="text-sm font-black text-slate-500 hover:text-white transition-colors">
            ← Back to Login
          </a>
        </div>
      </div>
    </div>
  );
}
