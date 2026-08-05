// =============================================================================
// job-hunter-dashboard/src/components/auth/VerifyEmail.jsx  — NEW FILE
// Handles both /verify-email (regular users) and /hr/verify (HR users)
// Reads ?token= from URL, calls the correct backend endpoint
// =============================================================================
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export default function VerifyEmail() {
  const [status, setStatus] = useState('loading'); // loading | success | error | hr_pending
  const [message, setMessage] = useState('');

  useEffect(() => {
    const params   = new URLSearchParams(window.location.search);
    const token    = params.get('token');
    const isHR     = window.location.pathname.includes('/hr/verify');
    const endpoint = isHR
      ? `${API_BASE_URL}/hr-auth/verify?token=${token}`
      : `${API_BASE_URL}/auth/verify-email?token=${token}`;

    if (!token) {
      setStatus('error');
      setMessage('Invalid verification link. Please request a new one.');
      return;
    }

    axios.get(endpoint)
      .then(res => {
        const msg = res.data?.message || '';
        if (msg.includes('pending') || msg.includes('approval')) {
          setStatus('hr_pending');
        } else {
          setStatus('success');
        }
        setMessage(msg);
      })
      .catch(err => {
        setStatus('error');
        setMessage(err.response?.data?.detail || 'Verification failed. The link may have expired.');
      });
  }, []);

  const isHR = window.location.pathname.includes('/hr/verify');

  const states = {
    loading: {
      icon: (
        <div className="w-20 h-20 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-6" />
      ),
      title: 'Verifying your email...',
      sub:   'Please wait a moment.',
      color: 'text-white',
    },
    success: {
      icon: <div className="w-20 h-20 bg-emerald-500/10 border-2 border-emerald-500/30 rounded-full flex items-center justify-center mx-auto mb-6"><span className="text-4xl">✅</span></div>,
      title: 'Email verified!',
      sub:   message || 'Your account is now active. Welcome to Baalebos Cloud!',
      color: 'text-emerald-400',
    },
    hr_pending: {
      icon: <div className="w-20 h-20 bg-blue-500/10 border-2 border-blue-500/30 rounded-full flex items-center justify-center mx-auto mb-6"><span className="text-4xl">⏳</span></div>,
      title: 'Email verified!',
      sub:   'Your HR account is now pending admin approval. You\'ll receive an email within 24–48 hours.',
      color: 'text-blue-400',
    },
    error: {
      icon: <div className="w-20 h-20 bg-rose-500/10 border-2 border-rose-500/30 rounded-full flex items-center justify-center mx-auto mb-6"><span className="text-4xl">❌</span></div>,
      title: 'Verification failed',
      sub:   message || 'Invalid or expired link.',
      color: 'text-rose-400',
    },
  };

  const s = states[status];

  return (
    <div className="app-canvas min-h-screen w-full flex items-center justify-center p-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />
      <div className="max-w-md w-full relative z-10 text-center">

        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className={`w-10 h-10 ${isHR ? 'bg-blue-500' : 'bg-emerald-500'} rounded-xl flex items-center justify-center shadow-lg`}>
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
          </div>
          <div className="text-left">
            <div className="text-white font-black text-lg tracking-tight">BAALEBOS CLOUD</div>
            <div className={`${isHR ? 'text-blue-400' : 'text-emerald-400'} text-[10px] font-bold uppercase tracking-[0.2em]`}>
              {isHR ? 'HR Portal' : 'AI Talent Infrastructure'}
            </div>
          </div>
        </div>

        {s.icon}

        <h1 className={`text-3xl font-black mb-3 ${s.color}`}
          style={{ fontFamily: "'Playfair Display', serif" }}>
          {s.title}
        </h1>
        <p className="text-slate-400 text-base leading-relaxed mb-8">{s.sub}</p>

        {/* HR pending steps */}
        {status === 'hr_pending' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-left mb-6">
            <p className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3">What happens next</p>
            {[
              ['🔍', 'Admin reviews your company details'],
              ['✅', 'You receive an approval email'],
              ['🚀', 'Log in and start posting jobs'],
            ].map(([icon, step]) => (
              <div key={step} className="flex gap-3 mb-2 last:mb-0">
                <span className="shrink-0">{icon}</span>
                <p className="text-sm text-slate-300 font-medium">{step}</p>
              </div>
            ))}
          </div>
        )}

        {/* CTAs */}
        <div className="space-y-3">
          {status === 'success' && (
            <a href={isHR ? '/hr' : '/'}
              className="block w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all shadow-xl shadow-emerald-600/20 text-center">
              Go to Dashboard →
            </a>
          )}
          {status === 'hr_pending' && (
            <a href="/hr/login"
              className="block w-full bg-blue-600 hover:bg-blue-500 text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all text-center">
              Go to HR Login →
            </a>
          )}
          {status === 'error' && (
            <a href={isHR ? '/hr/signup' : '/signup'}
              className="block w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all text-center">
              Back to Signup →
            </a>
          )}
          <a href={isHR ? '/hr/login' : '/login'}
            className="block w-full border-2 border-slate-800 hover:border-slate-600 text-slate-400 hover:text-white font-black py-4 rounded-2xl text-sm uppercase tracking-widest transition-all text-center">
            ← Back to Login
          </a>
        </div>
      </div>
    </div>
  );
}
