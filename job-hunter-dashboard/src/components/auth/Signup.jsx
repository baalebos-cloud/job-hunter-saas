import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://baalebo.xyz";

export default function Signup() {
  const [formData, setFormData] = useState({ name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
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
      <div className="w-full max-w-md bg-white p-8 rounded-3xl shadow-xl border border-slate-100">
        <h1 className="text-2xl font-bold text-slate-900 mb-2 text-center">Join Baalebos Cloud</h1>
        <p className="text-slate-500 text-sm text-center mb-8">Start your AI-powered career journey.</p>
        
        {error && <div className="mb-4 p-3 bg-rose-50 text-rose-600 rounded-lg text-xs font-bold">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <input 
            type="text" placeholder="Full Name" required
            className="w-full p-4 rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500"
            onChange={(e) => setFormData({...formData, name: e.target.value})}
          />
          <input 
            type="email" placeholder="Email Address" required
            className="w-full p-4 rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500"
            onChange={(e) => setFormData({...formData, email: e.target.value})}
          />
          <input 
            type="password" placeholder="Password" required
            className="w-full p-4 rounded-xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500"
            onChange={(e) => setFormData({...formData, password: e.target.value})}
          />
          <button 
            type="submit" disabled={loading}
            className="w-full bg-emerald-600 text-white py-4 rounded-xl font-bold hover:bg-emerald-700 transition-all shadow-lg"
          >
            {loading ? "Creating Account..." : "Claim My Results →"}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account? <a href="/login" className="text-emerald-600 font-bold hover:underline">Login</a>
        </p>
      </div>
    </div>
  );
}
