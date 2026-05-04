import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-blue-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600';
const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2';

export default function HRSignup() {
  const [form, setForm] = useState({ name: '', email: '', password: '', company_name: '', country: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/signup`, {
        full_name: form.name,
        email: form.email,
        password: form.password,
        company_name: form.company_name,
        country: form.country || null,
        is_hr: true,
        career_track: null,
      });
      const token = res.data.access_token || res.data.token || null;
      if (token?.trim()) {
        localStorage.setItem('token', token.trim());
        window.location.href = '/hr';
      } else {
        window.location.href = '/login';
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Left panel */}
      <div className="hidden lg:flex lg:w-[45%] relative flex-col justify-between p-14 overflow-hidden">
        <img src="https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&q=85"
          alt="office" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/95 via-slate-900/88 to-blue-950/80" />

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
            Post Jobs.<br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
              Find Top Talent.
            </span><br/>
            Hire Faster.
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed max-w-xs">
            Post your jobs to 80+ countries. See ATS scores for every applicant. Schedule interviews directly from your dashboard.
          </p>
          <div className="flex gap-6 mt-6">
            {[['Free', 'To Post Jobs'], ['Instant', 'Go Live'], ['Global', 'Reach']].map(([v, l]) => (
              <div key={l}>
                <div className="text-xl font-black text-white">{v}</div>
                <div className="text-xs text-slate-500 font-semibold mt-0.5">{l}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-xs text-slate-600">
          © {new Date().getFullYear()} Baalebos Cloud
        </div>
      </div>

      {/* Right form */}
      <div className="w-full lg:w-[55%] flex items-center justify-center p-8 bg-slate-950 overflow-y-auto">
        <div className="w-full max-w-lg py-8">

          <div className="mb-8">
            <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-2 mb-4">
              <span className="w-2 h-2 bg-blue-400 rounded-full" />
              <span className="text-blue-400 text-xs font-bold uppercase tracking-widest">HR Registration</span>
            </div>
            <h1 className="text-3xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
              Create HR Account
            </h1>
            <p className="text-slate-400 text-sm font-medium mt-2">
              Post jobs, review applicants, and hire top global tech talent.
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-2xl text-sm font-bold flex items-center gap-2">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={labelCls}>Your Full Name</label>
              <input type="text" required placeholder="e.g. Sarah Johnson" className={inputCls}
                value={form.name} onChange={e => set('name', e.target.value)} />
            </div>

            <div>
              <label className={labelCls}>Company Name</label>
              <input type="text" required placeholder="e.g. Acme Technologies Ltd" className={inputCls}
                value={form.company_name} onChange={e => set('company_name', e.target.value)} />
            </div>

            <div>
              <label className={labelCls}>Work Email</label>
              <input type="email" required placeholder="you@company.com" className={inputCls}
                value={form.email} onChange={e => set('email', e.target.value)} />
            </div>

            <div>
              <label className={labelCls}>Password</label>
              <input type="password" required placeholder="Min. 8 characters" className={inputCls}
                value={form.password} onChange={e => set('password', e.target.value)} />
            </div>

            <div>
              <label className={labelCls}>Country</label>
              <input type="text" placeholder="e.g. Nigeria, United States, Germany" className={inputCls}
                value={form.country} onChange={e => set('country', e.target.value)} />
            </div>

            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-blue-500 active:scale-[0.98] transition-all shadow-xl shadow-blue-600/20 disabled:bg-slate-700 disabled:cursor-not-allowed mt-2">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Creating Account...
                </span>
              ) : 'Create HR Account & Post Jobs →'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800 space-y-3 text-center">
            <p className="text-sm text-slate-500 font-medium">
              Already have an HR account?{' '}
              <a href="/login" className="text-blue-400 font-black hover:text-blue-300 transition-colors">Sign in →</a>
            </p>
            <p className="text-sm text-slate-600 font-medium">
              Looking for a job instead?{' '}
              <a href="/signup" className="text-emerald-400 font-black hover:text-emerald-300 transition-colors">Job Seeker Signup →</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
