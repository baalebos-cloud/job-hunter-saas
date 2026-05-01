import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export default function Login() {
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // SAFETY: If already logged in, send to dashboard immediately
  useEffect(() => {
    if (localStorage.getItem("token")) {
      window.location.href = "/";
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await axios.post(`${API_BASE_URL}/auth/login`, {
        email: formData.email,
        password: formData.password
      });

      // TOKEN FIX: Check all common token field names your backend might return
      const token =
        res.data.access_token ||
        res.data.token ||
        res.data.accessToken ||
        res.data.jwt ||
        null;

      if (token && typeof token === 'string' && token.trim() !== '') {
        // TOKEN FIX: Ensure token is cleanly stored with no whitespace
        localStorage.setItem("token", token.trim());
        // TOKEN FIX: Verify it was actually saved before redirecting
        if (localStorage.getItem("token")) {
          window.location.href = '/';
        } else {
          setError("Session could not be saved. Please check your browser settings.");
        }
      } else {
        setError("Login successful but no token received. Please contact support.");
      }
    } catch (err) {
      console.error("Login detail:", err.response?.data);
      setError(err.response?.data?.detail || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6 font-sans">
      <div className="w-full max-w-md bg-white p-10 rounded-3xl shadow-2xl border border-slate-100">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Welcome Back</h1>
          <p className="text-slate-500 mt-2 font-medium">Access your AI Career Engine</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-rose-50 border border-rose-100 text-rose-600 rounded-2xl text-xs font-bold flex items-center gap-2">
            <span>⚠️</span> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">
              Email Address
            </label>
            {/* INPUT FIX: Added !text-slate-900 (important) to override global body color:white from index.css */}
            <input
              type="email"
              required
              className="w-full px-5 py-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all !text-slate-900 font-bold placeholder:text-slate-300"
              style={{ color: '#0f172a' }}
              placeholder="name@company.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">
              Password
            </label>
            {/* INPUT FIX: Added !text-slate-900 (important) + inline style as fallback */}
            <input
              type="password"
              required
              className="w-full px-5 py-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all !text-slate-900 font-bold placeholder:text-slate-300"
              style={{ color: '#0f172a' }}
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-slate-900 text-white py-4 rounded-2xl font-black uppercase tracking-widest hover:bg-emerald-600 active:scale-[0.98] transition-all shadow-xl shadow-slate-900/20 disabled:bg-slate-300"
          >
            {loading ? "Verifying..." : "Access Dashboard →"}
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-slate-500 font-medium">
          Need an engine account?{' '}
          <a href="/signup" className="text-emerald-600 font-black hover:underline underline-offset-4">
            Sign Up
          </a>
        </p>
      </div>
    </div>
  );
}