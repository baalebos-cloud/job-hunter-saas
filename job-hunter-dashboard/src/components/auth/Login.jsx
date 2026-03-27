import React, { useState } from 'react';
import axios from 'axios';

export default function Login() {
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Momentum check: did they have a resume waiting for download?
  const pendingId = localStorage.getItem("pending_download_id");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await axios.post('http://127.0.0.1:8000/auth/login', formData);
      
      // 1. Save the token
      localStorage.setItem("token", res.data.access_token);
      
      // 2. MOMENTUM REDIRECT: If they had a pending resume, download it now
      if (pendingId) {
        window.location.href = `http://127.0.0.1:8000/resume/download/${pendingId}`;
        localStorage.removeItem("pending_download_id"); // Clear after use
      } else {
        window.location.href = '/';
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid email or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col md:flex-row">
      {/* 🟦 Left Side: Branding (Consistent with Signup) */}
      <div className="hidden md:flex md:w-1/2 bg-slate-900 p-12 flex-col justify-between text-white">
        <div>
          <div className="text-2xl font-bold tracking-tighter mb-2">Baalebos Cloud</div>
          <div className="h-1 w-12 bg-emerald-500 rounded-full"></div>
        </div>
        
        <div className="space-y-4">
          <h2 className="text-3xl font-bold">Welcome Back.</h2>
          <p className="text-slate-400 text-lg">
            Ready to track your next global tech move? Log in to access your dashboard.
          </p>
        </div>

        <div className="text-sm text-slate-500 italic">
          "The best way to predict the future is to create it."
        </div>
      </div>

      {/* ⬜ Right Side: Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 md:p-16">
        <div className="w-full max-w-md space-y-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Sign In</h1>
            <p className="text-slate-500 mt-2">Enter your credentials to continue.</p>
          </div>

          {error && (
            <div className="bg-rose-50 border border-rose-100 text-rose-600 px-4 py-3 rounded-xl text-sm font-medium">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Email Address</label>
              <input 
                type="email" required
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 outline-none transition-all"
                placeholder="name@company.com"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
              />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-sm font-bold text-slate-700">Password</label>
                <a href="#" className="text-xs text-emerald-600 font-bold hover:underline">Forgot?</a>
              </div>
              <input 
                type="password" required
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 outline-none transition-all"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
              />
            </div>

            <button 
              type="submit"
              disabled={loading}
              className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold hover:bg-slate-800 transform active:scale-[0.98] transition-all shadow-lg shadow-slate-200 flex items-center justify-center gap-2"
            >
              {loading ? (
                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
              ) : "Sign In to Dashboard"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500">
            New to Baalebos? <a href="/signup" className="text-emerald-600 font-bold hover:underline">Create an account</a>
          </p>
        </div>
      </div>
    </div>
  );
}
