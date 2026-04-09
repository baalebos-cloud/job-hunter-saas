import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://baalebo.xyz/api/v1";

export default function Signup() {
  const [formData, setFormData] = useState({ name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Logic Match: Your backend auth.py uses 'UserCreate' which expects 'full_name'
      const res = await axios.post(`${API_BASE_URL}/auth/signup`, {
        full_name: formData.name,
        email: formData.email,
        password: formData.password
      });

      // Capture the token so the user is logged in immediately
      const token = res.data.access_token || res.data.token;
      if (token) {
        localStorage.setItem("token", token);
        window.location.href = '/'; // Go to Dashboard
      } else {
        window.location.href = '/login';
      }
    } catch (err) {
      console.error("Signup error:", err.response?.data);
      setError(err.response?.data?.detail || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6 font-sans">
      <div className="w-full max-w-md bg-white p-10 rounded-[2.5rem] shadow-2xl border border-slate-100">
        <h1 className="text-3xl font-black text-slate-900 mb-2 text-center tracking-tight">Join Baalebos Cloud</h1>
        <p className="text-slate-500 text-sm text-center mb-8 font-medium uppercase tracking-widest text-[10px]">Start your AI-powered career journey</p>

        {error && (
          <div className="mb-6 p-4 bg-rose-50 border border-rose-100 text-rose-600 rounded-2xl text-xs font-bold flex items-center gap-2">
            <span>⚠️</span> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">Full Name</label>
            <input
              type="text" 
              placeholder="Full Name" 
              required
              // CSS FIX: text-slate-900 and font-bold for visibility
              className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all text-slate-900 font-bold placeholder:text-slate-300"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">Email Address</label>
            <input
              type="email" 
              placeholder="Email Address" 
              required
              // CSS FIX: text-slate-900 and font-bold for visibility
              className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all text-slate-900 font-bold placeholder:text-slate-300"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">Password</label>
            <input
              type="password" 
              placeholder="Password" 
              required
              // CSS FIX: text-slate-900 and font-bold for visibility
              className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all text-slate-900 font-bold placeholder:text-slate-300"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
            />
          </div>

          <button
            type="submit" 
            disabled={loading}
            className="w-full bg-emerald-600 text-white py-5 rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-emerald-500 active:scale-[0.98] transition-all shadow-xl shadow-emerald-600/20 disabled:bg-slate-300"
          >
            {loading ? "Initializing..." : "Claim My Results →"}
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-slate-500 font-medium">
          Already have an account? <a href="/login" className="text-emerald-600 font-black hover:underline underline-offset-4">Login</a>
        </p>
      </div>
    </div>
  );
}
