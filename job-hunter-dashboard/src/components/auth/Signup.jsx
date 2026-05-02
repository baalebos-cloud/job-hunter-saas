import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const CAREER_TRACKS = [
  { value: 'Frontend Developer', label: '🎨 Frontend Developer' },
  { value: 'Backend Engineer', label: '⚙️ Backend Engineer' },
  { value: 'Full Stack Developer', label: '🔥 Full Stack Developer' },
  { value: 'DevOps Engineer', label: '🚀 DevOps Engineer' },
  { value: 'Cloud Engineer', label: '☁️ Cloud Engineer' },
  { value: 'Data Engineer', label: '📊 Data Engineer' },
  { value: 'Data Scientist', label: '🧠 Data Scientist' },
  { value: 'Machine Learning Engineer', label: '🤖 ML Engineer' },
  { value: 'Cybersecurity Engineer', label: '🔒 Cybersecurity' },
  { value: 'Product Manager', label: '📋 Product Manager' },
  { value: 'UI/UX Designer', label: '✏️ UI/UX Designer' },
  { value: 'Mobile Developer', label: '📱 Mobile Developer' },
  { value: 'QA Engineer', label: '🧪 QA Engineer' },
  { value: 'Platform Engineer', label: '🏗️ Platform Engineer' },
  { value: 'Software Engineer', label: '💻 Software Engineer' },
];

const COUNTRIES = [
  'Worldwide / Remote','Nigeria','United States','United Kingdom','Canada','Germany',
  'France','Netherlands','Sweden','Norway','Denmark','Finland','Switzerland','Austria',
  'Belgium','Ireland','Spain','Portugal','Italy','Poland','Czech Republic','Romania',
  'Hungary','Ukraine','Turkey','Israel','UAE','Saudi Arabia','South Africa','Kenya',
  'Ghana','Egypt','India','Pakistan','Bangladesh','Sri Lanka','Singapore','Malaysia',
  'Indonesia','Philippines','Vietnam','Thailand','Japan','South Korea','China','Taiwan',
  'Hong Kong','Australia','New Zealand','Brazil','Argentina','Mexico','Colombia','Chile',
  'Peru','Venezuela','Ecuador','Bolivia','Uruguay','Paraguay','Costa Rica','Panama',
  'Jamaica','Trinidad and Tobago','Ethiopia','Tanzania','Uganda','Rwanda','Senegal',
  'Ivory Coast','Cameroon','Zimbabwe','Zambia','Mozambique','Morocco','Tunisia','Algeria',
];

const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-800 bg-slate-900 outline-none focus:border-emerald-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600';
const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2';

export default function Signup() {
  const [form, setForm] = useState({ name: '', email: '', password: '', career_track: '', country: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/signup`, {
        full_name: form.name, email: form.email,
        password: form.password, career_track: form.career_track || null,
        country: form.country || null,
      });
      const token = res.data.access_token || res.data.token || null;
      if (token?.trim()) { localStorage.setItem('token', token.trim()); window.location.href = '/'; }
      else window.location.href = '/login';
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed. Please try again.');
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* ── Left hero panel ── */}
      <div className="hidden lg:flex lg:w-[45%] relative flex-col justify-between p-14 overflow-hidden">
        <img src="https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1200&q=85"
          alt="tech" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/95 via-slate-900/88 to-emerald-950/80" />

        {/* Floating stats */}
        <div className="absolute top-28 right-10 bg-slate-900/80 backdrop-blur border border-emerald-500/20 rounded-2xl p-5 shadow-2xl">
          <div className="text-xs text-slate-500 font-bold uppercase tracking-widest mb-3">Live Stats</div>
          {[['🌍', '80+ Countries', 'text-blue-400'], ['⚡', '5-min Refresh', 'text-emerald-400'], ['🎯', '94% Avg ATS', 'text-amber-400']].map(([icon, label, cls]) => (
            <div key={label} className="flex items-center gap-2 mb-2 last:mb-0">
              <span>{icon}</span>
              <span className={`text-sm font-bold ${cls}`}>{label}</span>
            </div>
          ))}
        </div>

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

        <div className="relative z-10">
          <h2 className="text-4xl font-black text-white leading-tight mb-4"
            style={{ fontFamily: "'Playfair Display', serif" }}>
            Join Engineers<br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-blue-400">
              Getting Hired
            </span><br/>
            Globally.
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed max-w-xs">
            From ATS optimization to interview — our AI guides every step of your global tech job search.
          </p>
        </div>

        <div className="relative z-10 text-xs text-slate-600 font-medium">
          © {new Date().getFullYear()} Baalebos Cloud
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="w-full lg:w-[55%] flex items-center justify-center p-8 bg-slate-950 overflow-y-auto">
        <div className="w-full max-w-lg py-8">

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
              Create your account
            </h1>
            <p className="text-slate-400 text-sm font-medium mt-2">Join engineers from 80+ countries finding global tech roles.</p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-2xl text-sm font-bold flex items-center gap-2">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={labelCls}>Full Name</label>
              <input type="text" required placeholder="e.g. Oluwadare Jayeola" className={inputCls}
                value={form.name} onChange={e => set('name', e.target.value)} />
            </div>

            <div>
              <label className={labelCls}>Email Address</label>
              <input type="email" required placeholder="you@company.com" className={inputCls}
                value={form.email} onChange={e => set('email', e.target.value)} />
            </div>

            <div>
              <label className={labelCls}>Password</label>
              <input type="password" required placeholder="Min. 8 characters" className={inputCls}
                value={form.password} onChange={e => set('password', e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Career Track</label>
                <div className="relative">
                  <select required
                    className={`${inputCls} appearance-none pr-8 cursor-pointer`}
                    style={{ color: form.career_track ? '#fff' : '#4b5563' }}
                    value={form.career_track} onChange={e => set('career_track', e.target.value)}>
                    <option value="" disabled>Select role...</option>
                    {CAREER_TRACKS.map(t => <option key={t.value} value={t.value} style={{ color: '#fff', background: '#0f172a' }}>{t.label}</option>)}
                  </select>
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none text-xs">▾</span>
                </div>
              </div>

              <div>
                <label className={labelCls}>Country 🌍</label>
                <div className="relative">
                  <select className={`${inputCls} appearance-none pr-8 cursor-pointer`}
                    style={{ color: form.country ? '#fff' : '#4b5563' }}
                    value={form.country} onChange={e => set('country', e.target.value)}>
                    <option value="" style={{ color: '#4b5563', background: '#0f172a' }}>Select country...</option>
                    {COUNTRIES.map(c => <option key={c} value={c} style={{ color: '#fff', background: '#0f172a' }}>{c}</option>)}
                  </select>
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none text-xs">▾</span>
                </div>
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="w-full bg-emerald-600 text-white py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-emerald-500 active:scale-[0.98] transition-all shadow-xl shadow-emerald-600/20 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed mt-2">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Creating Account...
                </span>
              ) : 'Start My Global Job Search →'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800 text-center">
            <p className="text-sm text-slate-500 font-medium">
              Already have an account?{' '}
              <a href="/login" className="text-emerald-400 font-black hover:text-emerald-300 transition-colors">Sign in →</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
