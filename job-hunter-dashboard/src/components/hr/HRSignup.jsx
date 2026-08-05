// =============================================================================
// job-hunter-dashboard/src/components/hr/HRSignup.jsx
// Company email validation + honest pending approval flow
// =============================================================================
import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const BLOCKED_DOMAINS = new Set([
  'gmail.com','yahoo.com','yahoo.co.uk','yahoo.co.in','ymail.com',
  'hotmail.com','hotmail.co.uk','outlook.com','outlook.co.uk',
  'live.com','live.co.uk','msn.com','icloud.com','me.com',
  'aol.com','protonmail.com','proton.me','tutanota.com',
  'zoho.com','mail.com','gmx.com','gmx.net','inbox.com',
  'yandex.com','yandex.ru','qq.com','163.com','126.com',
]);

const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-blue-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600';
const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2';

const validateCompanyEmail = (email) => {
  const domain = email.toLowerCase().split('@')[1] || '';
  if (BLOCKED_DOMAINS.has(domain)) {
    return `Please use your company work email. Free providers like ${domain} are not accepted.`;
  }
  return null;
};

export default function HRSignup() {
  const [form, setForm] = useState({
    name: '', email: '', password: '', company_name: '',
    job_title: '', country: '', linkedin_url: '', company_url: '',
  });
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [emailError, setEmailError] = useState('');
  const [success, setSuccess]   = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleEmailChange = (e) => {
    const val = e.target.value;
    set('email', val);
    if (val.includes('@')) {
      const err = validateCompanyEmail(val);
      setEmailError(err || '');
    } else {
      setEmailError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const emailErr = validateCompanyEmail(form.email);
    if (emailErr) { setEmailError(emailErr); return; }
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!form.company_name.trim()) { setError('Company name is required.'); return; }

    setLoading(true); setError('');
    try {
      await axios.post(`${API_BASE_URL}/hr-auth/signup`, {
        full_name:    form.name,
        email:        form.email,
        password:     form.password,
        company_name: form.company_name,
        job_title:    form.job_title || 'HR Manager',
        country:      form.country || null,
        linkedin_url: form.linkedin_url || '',
        company_url:  form.company_url || '',
      });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally { setLoading(false); }
  };

  // ── Success state ─────────────────────────────────────────────────────────
  if (success) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="max-w-md w-full text-center">
        <div className="w-20 h-20 bg-blue-500/10 border-2 border-blue-500/30 rounded-full flex items-center justify-center mx-auto mb-6">
          <span className="text-4xl">📬</span>
        </div>
        <h1 className="text-3xl font-black text-white mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
          Check your inbox
        </h1>
        <p className="text-slate-400 text-base leading-relaxed mb-6">
          We've sent a verification link to <span className="text-blue-400 font-bold">{form.email}</span>.
          Click it to confirm your email address.
        </p>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-left space-y-3 mb-6">
          {[
            ['📧', 'Verify your email', 'Click the link we just sent you'],
            ['🔍', 'Account review', 'Our team verifies your company details (24–48 hrs)'],
            ['✅', 'Get approved', 'Receive an approval email to start posting jobs'],
          ].map(([icon, title, desc]) => (
            <div key={title} className="flex gap-3">
              <span className="text-xl shrink-0">{icon}</span>
              <div>
                <p className="text-sm font-black text-white">{title}</p>
                <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
        <a href="/hr/login" className="block w-full bg-blue-600 hover:bg-blue-500 text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all text-center">
          Go to HR Login →
        </a>
      </div>
    </div>
  );

  return (
    <div className="app-canvas min-h-screen w-full flex" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />

      {/* Left panel */}
      <div className="hidden lg:flex lg:w-[45%] min-w-0 relative flex-col justify-between p-14 overflow-hidden z-10">
        <img src="https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&q=85"
          alt="office" className="absolute inset-0 w-full h-full object-cover opacity-40 mix-blend-luminosity" />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/95 via-slate-900/88 to-blue-950/80" />

        {/* Verification badge */}
        <div className="absolute top-24 right-8 bg-slate-900/90 backdrop-blur border border-blue-500/20 rounded-2xl p-4 shadow-xl">
          <div className="text-xs text-slate-500 font-bold uppercase tracking-widest mb-2">Verification Process</div>
          {[['✉️','Email verified','Instant'],['🔍','Company reviewed','24–48 hrs'],['✅','Account approved','Start posting']].map(([icon,step,time]) => (
            <div key={step} className="flex items-center gap-2 mb-1.5 last:mb-0">
              <span>{icon}</span>
              <span className="text-xs font-bold text-white">{step}</span>
              <span className="text-xs text-slate-500 ml-auto">{time}</span>
            </div>
          ))}
        </div>

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
            </svg>
          </div>
          <div>
            <div className="text-white font-black text-lg tracking-tight">BAALEBOS CLOUD</div>
            <div className="text-blue-400 text-[10px] font-bold uppercase tracking-[0.2em]">HR Portal — Verified Companies Only</div>
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
            Verified HR accounts only. We review every company to keep our talent pool trusted and spam-free.
          </p>
          <div className="flex gap-6 mt-6">
            {[['Free','To Post Jobs'],['Verified','Companies Only'],['Global','80+ Countries']].map(([v,l]) => (
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
      <div className="w-full lg:w-[55%] min-w-0 flex-1 flex items-center justify-center p-8 relative z-10 overflow-y-auto">
        <div className="w-full max-w-lg py-8">

          <div className="mb-6">
            <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-2 mb-4">
              <span className="w-2 h-2 bg-blue-400 rounded-full" />
              <span className="text-blue-400 text-xs font-bold uppercase tracking-widest">Company Work Email Required</span>
            </div>
            <h1 className="text-3xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
              Create HR Account
            </h1>
            <p className="text-slate-400 text-sm font-medium mt-2">
              Post jobs and access a global pool of verified tech talent.
            </p>
          </div>

          {/* Company email warning */}
          <div className="mb-5 p-4 bg-amber-500/10 border border-amber-500/20 rounded-2xl flex gap-3">
            <span className="text-amber-400 shrink-0 mt-0.5">⚠️</span>
            <p className="text-amber-300 text-xs font-medium leading-relaxed">
              <strong className="font-black">Company work email required.</strong> Gmail, Yahoo, Hotmail and other
              free providers are not accepted. Use your official company email (e.g. you@yourcompany.com).
            </p>
          </div>

          {error && (
            <div className="mb-5 p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-2xl text-sm font-bold">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={labelCls}>Your Full Name *</label>
              <input type="text" required placeholder="e.g. Sarah Johnson" className={inputCls}
                value={form.name} onChange={e => set('name', e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Company Name *</label>
                <input type="text" required placeholder="Acme Technologies Ltd" className={inputCls}
                  value={form.company_name} onChange={e => set('company_name', e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Your Job Title</label>
                <input type="text" placeholder="e.g. HR Manager" className={inputCls}
                  value={form.job_title} onChange={e => set('job_title', e.target.value)} />
              </div>
            </div>

            <div>
              <label className={labelCls}>Company Work Email *</label>
              <input type="email" required placeholder="you@yourcompany.com" className={`${inputCls} ${emailError ? 'border-rose-500' : ''}`}
                value={form.email} onChange={handleEmailChange} />
              {emailError && <p className="text-rose-400 text-xs font-bold mt-1.5">❌ {emailError}</p>}
              {form.email.includes('@') && !emailError && (
                <p className="text-emerald-400 text-xs font-bold mt-1.5">✓ Company email accepted</p>
              )}
            </div>

            <div>
              <label className={labelCls}>Password *</label>
              <input type="password" required placeholder="Min. 8 characters" className={inputCls}
                value={form.password} onChange={e => set('password', e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Company Website</label>
                <input type="url" placeholder="https://yourcompany.com" className={inputCls}
                  value={form.company_url} onChange={e => set('company_url', e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Your LinkedIn</label>
                <input type="url" placeholder="https://linkedin.com/in/..." className={inputCls}
                  value={form.linkedin_url} onChange={e => set('linkedin_url', e.target.value)} />
              </div>
            </div>

            <div>
              <label className={labelCls}>Country</label>
              <input type="text" placeholder="e.g. Nigeria, United States" className={inputCls}
                value={form.country} onChange={e => set('country', e.target.value)} />
            </div>

            <button type="submit" disabled={loading || !!emailError}
              className="w-full bg-blue-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-blue-500 active:scale-[0.98] transition-all shadow-xl shadow-blue-600/20 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed mt-2">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Submitting...
                </span>
              ) : 'Submit HR Application →'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800 space-y-3 text-center">
            <p className="text-sm text-slate-500">
              Already have an HR account?{' '}
              <a href="/hr/login" className="text-blue-400 font-black hover:text-blue-300 transition-colors">Sign in →</a>
            </p>
            <p className="text-sm text-slate-600">
              Looking for a job?{' '}
              <a href="/signup" className="text-emerald-400 font-black hover:text-emerald-300 transition-colors">Job Seeker Signup →</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
