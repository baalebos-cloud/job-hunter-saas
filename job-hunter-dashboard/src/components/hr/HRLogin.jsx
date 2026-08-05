// =============================================================================
// job-hunter-dashboard/src/components/hr/HRLogin.jsx
// Dedicated HR login — company email only, clear error states
// =============================================================================
import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const BLOCKED_DOMAINS = new Set([
  'gmail.com','yahoo.com','yahoo.co.uk','hotmail.com','outlook.com',
  'live.com','icloud.com','me.com','aol.com','protonmail.com','proton.me',
]);

const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-blue-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600';
const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2';

export default function HRLogin() {
  const [form, setForm]     = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');
  const [emailError, setEmailError] = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleEmailChange = (e) => {
    const val = e.target.value;
    set('email', val);
    if (val.includes('@')) {
      const domain = val.toLowerCase().split('@')[1] || '';
      setEmailError(BLOCKED_DOMAINS.has(domain)
        ? `HR login requires a company work email. ${domain} is not accepted.`
        : '');
    } else {
      setEmailError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (emailError) return;
    setLoading(true); setError('');
    try {
      const res = await axios.post(`${API_BASE_URL}/hr-auth/login`, {
        email:    form.email,
        password: form.password,
      });
      const token = res.data.access_token;
      if (token) {
        localStorage.setItem('token', token.trim());
        window.location.href = res.data.redirect || '/hr';
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(detail);
    } finally { setLoading(false); }
  };

  return (
    <div className="app-canvas min-h-screen w-full flex" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />

      {/* Left panel */}
      <div className="hidden lg:flex lg:w-[45%] min-w-0 relative flex-col justify-between p-14 overflow-hidden z-10">
        <img src="https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&q=85"
          alt="office" className="absolute inset-0 w-full h-full object-cover opacity-70 mix-blend-luminosity" />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/70 via-slate-900/55 to-blue-950/45" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
            </svg>
          </div>
          <div>
            <div className="text-white font-black text-lg tracking-tight">BAALEBOS CLOUD</div>
            <div className="text-blue-400 text-[10px] font-bold uppercase tracking-[0.2em]">HR Portal</div>
          </div>
        </div>

        <div className="relative z-10">
          <h2 className="text-4xl font-black text-white leading-tight mb-4"
            style={{ fontFamily: "'Playfair Display', serif" }}>
            Welcome back,<br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
              HR Professional.
            </span>
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed max-w-xs">
            Access your HR dashboard, manage job postings, and review applicants with ATS scores.
          </p>
          <div className="flex gap-6 mt-6">
            {[['Live','Job Feed'],['ATS','Scoring'],['Global','Applicants']].map(([v,l]) => (
              <div key={l}>
                <div className="text-xl font-black text-white">{v}</div>
                <div className="text-xs text-slate-500 font-semibold mt-0.5">{l}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative z-10 text-xs text-slate-600">© {new Date().getFullYear()} Baalebos Cloud</div>
      </div>

      {/* Right form */}
      <div className="w-full lg:w-[55%] min-w-0 flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="w-full max-w-md">

          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
              </svg>
            </div>
            <span className="font-black text-white text-lg">BAALEBOS HR</span>
          </div>

          <div className="mb-8">
            <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-2 mb-4">
              <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
              <span className="text-blue-400 text-xs font-bold uppercase tracking-widest">HR Portal Login</span>
            </div>
            <h1 className="text-3xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
              Sign in to HR Portal
            </h1>
            <p className="text-slate-400 text-sm font-medium mt-2">
              Company work email required. Free email providers are blocked.
            </p>
          </div>

          {/* Error states with specific guidance */}
          {error && (
            <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl">
              <p className="text-rose-400 text-sm font-bold mb-1">⚠️ {error}</p>
              {error.includes('not verified') && (
                <p className="text-rose-300 text-xs mt-1">
                  Check your inbox for the verification email we sent when you registered.
                </p>
              )}
              {error.includes('not registered as an HR') && (
                <p className="text-rose-300 text-xs mt-1">
                  Need an HR account?{' '}
                  <a href="/hr/signup" className="font-black underline">Apply here →</a>
                </p>
              )}
              {error.includes('pending') && (
                <p className="text-amber-300 text-xs mt-1 font-medium">
                  Your account is awaiting admin approval. You'll receive an email once approved (24–48 hrs).
                </p>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={labelCls}>Company Work Email</label>
              <input type="email" required placeholder="you@yourcompany.com"
                className={`${inputCls} ${emailError ? 'border-rose-500' : ''}`}
                value={form.email} onChange={handleEmailChange} />
              {emailError && <p className="text-rose-400 text-xs font-bold mt-1.5">❌ {emailError}</p>}
              {form.email.includes('@') && !emailError && (
                <p className="text-emerald-400 text-xs font-bold mt-1.5">✓ Company email accepted</p>
              )}
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className={labelCls} style={{ margin: 0 }}>Password</label>
                <a href="/hr/forgot-password" className="text-xs font-bold text-blue-400 hover:text-blue-300 transition-colors">
                  Forgot password?
                </a>
              </div>
              <input type="password" required placeholder="Your password" className={inputCls}
                value={form.password} onChange={e => set('password', e.target.value)} />
            </div>

            <button type="submit" disabled={loading || !!emailError}
              className="w-full bg-blue-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-blue-500 active:scale-[0.98] transition-all shadow-xl shadow-blue-600/20 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed mt-2">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Signing in...
                </span>
              ) : 'Sign in to HR Portal →'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800 space-y-3 text-center">
            <p className="text-sm text-slate-500">
              Don't have an HR account?{' '}
              <a href="/hr/signup" className="text-blue-400 font-black hover:text-blue-300 transition-colors">Apply here →</a>
            </p>
            <p className="text-sm text-slate-600">
              Looking for a job?{' '}
              <a href="/login" className="text-emerald-400 font-black hover:text-emerald-300 transition-colors">Job Seeker Login →</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
