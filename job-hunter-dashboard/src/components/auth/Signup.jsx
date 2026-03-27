import React, { useState } from 'react';
import axios from 'axios';

export default function Signup() {
  const [formData, setFormData] = useState({ email: '', password: '', fullName: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Momentum Hook: Retrieve the guest resume ID from the previous step
  const pendingId = localStorage.getItem("pending_download_id");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // 1. Create the account
      const res = await axios.post('http://127.0.0.1:8000/auth/signup', {
        email: formData.email,
        password: formData.password,
        full_name: formData.fullName // Match the backend Pydantic schema
      });

      const token = res.data.access_token;
      localStorage.setItem("token", token);

      // 2. MOMENTUM CLAIM: Link the guest resume to the new user account
      if (pendingId) {
        await axios.post(`http://127.0.0.1:8000/resume/claim/${pendingId}`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });

        // 3. TRIGGER DOWNLOAD: Direct download of the PDF they earned
        window.location.href = `http://127.0.0.1:8000/resume/download/${pendingId}`;
        localStorage.removeItem("pending_download_id");
      } else {
        // Regular signup flow
        window.location.href = '/';
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Signup failed. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col md:flex-row">
      {/* 🟦 Left Side: Branding & Value Proposition */}
      <div className="hidden md:flex md:w-1/2 bg-slate-900 p-12 flex-col justify-between text-white">
        <div>
          <div className="text-2xl font-bold tracking-tighter mb-2 italic text-emerald-400">BAALEBOS CLOUD</div>
          <div className="h-1 w-12 bg-emerald-500 rounded-full"></div>
        </div>

        <div className="space-y-6">
          <h2 className="text-4xl font-bold leading-tight">
            Unlock your <span className="text-emerald-400 font-mono italic underline decoration-slate-700 underline-offset-8">Global Tech</span> potential.
          </h2>
          <ul className="space-y-4 text-slate-300">
            <li className="flex items-center gap-3">
              <span className="text-emerald-500 bg-emerald-500/10 p-1 rounded-md italic font-black">AI</span> Advanced Resume ATS Optimization
            </li>
            <li className="flex items-center gap-3">
              <span className="text-emerald-500">✔</span> Real-time Cloud Career Tracker
            </li>
            <li className="flex items-center gap-3">
              <span className="text-emerald-500 font-mono">01</span> Direct Tech Benchmark Comparison
            </li>
          </ul>
        </div>

        <div className="text-sm text-slate-500 font-mono">
          SYSTEM_DEPLOY: 2026.03 // BAALEBOS_SECURE_AUTH
        </div>
      </div>

      {/* ⬜ Right Side: Signup Form */}
      <div className="flex-1 flex items-center justify-center p-8 md:p-16 bg-slate-50/30">
        <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100">
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight">Create Account</h1>
            <p className="text-slate-500 mt-2">
              {pendingId
                ? "Sign up to claim your AI-optimized resume PDF."
                : "Step into the global talent engine."}
            </p>
          </div>

          {error && (
            <div className="bg-rose-50 border border-rose-100 text-rose-600 px-4 py-3 rounded-xl text-sm font-medium animate-shake">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Full Name</label>
              <input
                type="text" required
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 outline-none transition-all placeholder:text-slate-300"
                placeholder="Ex: John Baalebos"
                onChange={(e) => setFormData({...formData, fullName: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Email Address</label>
              <input
                type="email" required
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 outline-none transition-all placeholder:text-slate-300"
                placeholder="name@cloud.com"
                onChange={(e) => setFormData({...formData, email: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Password</label>
              <input
                type="password" required
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 outline-none transition-all placeholder:text-slate-300"
                placeholder="••••••••"
                onChange={(e) => setFormData({...formData, password: e.target.value})}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-slate-900 text-white py-4 rounded-xl font-black uppercase tracking-tighter hover:bg-slate-800 transform active:scale-[0.98] transition-all shadow-xl shadow-slate-900/20 disabled:opacity-50"
            >
              {loading ? "Initializing..." : "Claim My Results"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500">
            Already a member? <a href="/login" className="text-emerald-600 font-black hover:underline underline-offset-4 decoration-2">Sign In</a>
          </p>
        </div>
      </div>
    </div>
  );
}
