// =============================================================================
// job-hunter-dashboard/src/components/auth/ForgotPassword.jsx
// =============================================================================
import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-emerald-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600';
const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2';

export default function ForgotPassword() {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent]       = useState(false);
  const [error, setError]     = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await axios.post(`${API_BASE_URL}/auth/forgot-password`, null, {
        params: { email }
      });
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally { setLoading(false); }
  };

  if (sent) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="max-w-md w-full text-center">
        <div className="w-20 h-20 bg-emerald-500/10 border-2 border-emerald-500/30 rounded-full flex items-center justify-center mx-auto mb-6">
          <span className="text-4xl">📬</span>
        </div>
        <h1 className="text-3xl font-black text-white mb-3"
          style={{ fontFamily: "'Playfair Display', serif" }}>Check your inbox</h1>
        <p className="text-slate-400 text-base leading-relaxed mb-6">
          If <span className="text-emerald-400 font-bold">{email}</span> is registered,
          we've sent a password reset link. Check your inbox and spam folder.
        </p>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-left mb-6">
          <p className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3">What to do next</p>
          {[
            ['📧', 'Open the email from Baalebos Cloud'],
            ['🔗', 'Click the "Reset My Password" button'],
            ['🔐', 'Set your new password — link expires in 1 hour'],
          ].map(([icon, step]) => (
            <div key={step} className="flex gap-3 mb-2 last:mb-0">
              <span className="shrink-0">{icon}</span>
              <p className="text-sm text-slate-300 font-medium">{step}</p>
            </div>
          ))}
        </div>
        <a href="/login"
          className="block w-full border-2 border-slate-800 hover:border-emerald-500/50 text-slate-400 hover:text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all text-center">
          ← Back to Login
        </a>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="w-full max-w-md">

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
            style={{ fontFamily: "'Playfair Display', serif" }}>Forgot your password?</h1>
          <p className="text-slate-400 text-sm font-medium">
            Enter your email address and we'll send you a reset link.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-2xl text-sm font-bold">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelCls}>Email Address</label>
            <input type="email" required placeholder="you@example.com" className={inputCls}
              value={email} onChange={e => setEmail(e.target.value)} />
          </div>

          <button type="submit" disabled={loading}
            className="w-full bg-emerald-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-emerald-500 active:scale-[0.98] transition-all shadow-xl shadow-emerald-600/20 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Sending...
              </span>
            ) : 'Send Reset Link →'}
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
