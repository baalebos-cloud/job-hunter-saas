import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export default function Login() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPass, setShowPass] = useState(false);

  useEffect(() => {
    if (localStorage.getItem('token')) window.location.href = '/';
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/login`, form);
      const token = res.data.access_token || res.data.token || null;
      if (token?.trim()) { localStorage.setItem('token', token.trim()); window.location.href = '/'; }
      else setError('Login succeeded but no token received.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid email or password.');
    } finally { setLoading(false); }
  };

  return (
    // FIX: w-full + min-w-0 on children prevents the flex row from collapsing
    // and leaving dead space — this is what caused the black void bug.
    <div className="app-canvas min-h-screen w-full flex" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />

      {/* ── Left hero panel ── */}
      <div className="hidden lg:flex lg:w-[55%] min-w-0 relative flex-col justify-between p-14 overflow-hidden z-10">
        <img src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1400&q=85"
          alt="tech" className="absolute inset-0 w-full h-full object-cover opacity-40 mix-blend-luminosity" />
        <div className="absolute inset-0 bg-gradient-to-br from-[#080b12]/95 via-[#0f172a]/90 to-emerald-950/70" />

        {/* Floating code snippets */}
        <div className="absolute top-32 right-16 bg-slate-900/80 backdrop-blur border border-emerald-500/20 rounded-2xl p-5 text-xs font-mono shadow-2xl z-10">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-3 h-3 rounded-full bg-rose-500"/>
            <span className="w-3 h-3 rounded-full bg-amber-500"/>
            <span className="w-3 h-3 rounded-full bg-emerald-500"/>
            <span className="text-slate-500 ml-2">ats_result.json</span>
          </div>
          <div className="text-slate-400">{'{'}</div>
          <div className="pl-4"><span className="text-blue-400">"ats_score"</span><span className="text-slate-400">: </span><span className="text-emerald-400">94</span><span className="text-slate-400">,</span></div>
          <div className="pl-4"><span className="text-blue-400">"status"</span><span className="text-slate-400">: </span><span className="text-amber-400">"interview"</span></div>
          <div className="text-slate-400">{'}'}</div>
        </div>

        <div className="absolute bottom-48 right-12 bg-slate-900/80 backdrop-blur border border-blue-500/20 rounded-2xl p-4 text-xs font-mono shadow-xl z-10">
          <div className="text-slate-500 mb-2">// AI Match Engine</div>
          <div><span className="text-purple-400">const</span> <span className="text-blue-300">match</span> <span className="text-slate-400">= </span><span className="text-emerald-400">97.3</span><span className="text-slate-400">%</span></div>
          <div><span className="text-purple-400">const</span> <span className="text-blue-300">role</span> <span className="text-slate-400">= </span><span className="text-amber-400">"DevOps Eng."</span></div>
        </div>

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
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

        {/* Hero text */}
        <div className="relative z-10">
          <h2 className="text-5xl font-black text-white leading-[1.1] mb-5"
            style={{ fontFamily: "'Playfair Display', serif" }}>
            Land Your<br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-amber-400">
              Dream Tech Job
            </span><br/>
            With AI.
          </h2>
          <p className="text-slate-400 text-base leading-relaxed mb-8 max-w-md">
            AI-powered resume optimization, real-time ATS scoring, and global job matching — all in one platform.
          </p>
          <div className="flex items-center gap-8">
            {[['94%', 'Avg ATS Score'], ['5 min', 'To Optimize'], ['80+', 'Countries']].map(([v, l]) => (
              <div key={l}>
                <div className="text-2xl font-black text-white">{v}</div>
                <div className="text-xs text-slate-500 font-semibold mt-0.5">{l}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-xs text-slate-600 font-medium">
          © {new Date().getFullYear()} Baalebos Cloud · Built for global engineers
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="w-full lg:w-[45%] min-w-0 flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="w-full max-w-md">

          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <span className="font-black text-white text-lg">BAALEBOS CLOUD</span>
          </div>

          <div className="mb-8">
            <h1 className="text-3xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
              Welcome back
            </h1>
            <p className="text-slate-400 text-sm font-medium mt-2">Sign in to your AI career dashboard</p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-2xl text-sm font-bold flex items-center gap-2">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Email</label>
              <input type="email" required placeholder="you@company.com"
                className="w-full px-4 py-4 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-emerald-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600"
                value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            </div>

            <div>
              <label className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Password</label>
              <div className="relative">
                <input type={showPass ? 'text' : 'password'} required placeholder="••••••••"
                  className="w-full px-4 py-4 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-emerald-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600 pr-16"
                  value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
                <button type="button" onClick={() => setShowPass(!showPass)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-emerald-400 text-xs font-black transition-colors">
                  {showPass ? 'HIDE' : 'SHOW'}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <a href="/forgot-password"
                className="text-xs font-black text-slate-500 hover:text-emerald-400 transition-colors">
                Forgot password?
              </a>
            </div>

            <button type="submit" disabled={loading}
              className="w-full bg-emerald-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-emerald-500 active:scale-[0.98] transition-all shadow-xl shadow-emerald-600/20 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Signing in...
                </span>
              ) : 'Sign In →'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800 text-center space-y-3">
            <p className="text-sm text-slate-500 font-medium">
              Don't have an account?{' '}
              <a href="/signup" className="text-emerald-400 font-black hover:text-emerald-300 transition-colors">
                Create one free →
              </a>
            </p>
            <p className="text-sm text-slate-600 font-medium">
              Are you an HR / Recruiter?{' '}
              <a href="/hr/signup" className="text-blue-400 font-black hover:text-blue-300 transition-colors">
                HR Portal →
              </a>
            </p>
          </div>

          <div className="flex items-center justify-center gap-6 mt-6">
            {['🔒 Secure', '⚡ Instant', '🌍 Global'].map(b => (
              <span key={b} className="text-xs font-bold text-slate-600">{b}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
