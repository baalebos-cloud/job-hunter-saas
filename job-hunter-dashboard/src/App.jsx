import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'

import DashboardLayout from './components/layout/DashboardLayout'
import StatsGrid from './components/StatsGrid'
import ApplicationsTable from './components/dashboard/ApplicationsTable'
import JobFeed from './components/JobFeed'
import ResumeUpload from './components/dashboard/ResumeUpload'
import AtsResultView from './components/dashboard/AtsResultView'
import Signup from './components/auth/Signup'
import Login from './components/auth/Login'
import ForgotPassword from './components/auth/ForgotPassword'
import ResetPassword from './components/auth/ResetPassword'
import VerifyEmail from './components/auth/VerifyEmail'
import AdminDashboard from './components/admin/AdminDashboard'
import HRPortal from './components/hr/HRPortal'
import HRSignup from './components/hr/HRSignup'
import HRLogin from './components/hr/HRLogin'
import ProfilePage from './components/ProfilePage'
import PricingPage from './components/PricingPage'
import ReferralDashboard from './components/ReferralDashboard'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// ── Auth guard — redirect to login if no token ────────────────────────────────
function RequireAuth({ children }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

// ── Role guard — blocks non-admin/HR users from restricted pages ─────────────
// FIX 3: Admin and HR pages are hidden from regular users, even via direct URL
function RequireRole({ role, children }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) { setLoading(false); return }
    axios.get(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setProfile(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [token])

  if (!token) return <Navigate to="/login" replace />
  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  )

  const hasAccess = role === 'admin' ? profile?.is_admin : (profile?.is_admin || profile?.is_hr)
  if (!hasAccess) return <Navigate to="/" replace />

  return children
}

// ── Overview page (/) ─────────────────────────────────────────────────────────
function OverviewPage() {
  const [data, setData]       = useState({ stats: null, apps: [] })
  const [loading, setLoading] = useState(true)
  const token = localStorage.getItem('token')

  const fetchData = useCallback(async () => {
    if (!token) { setLoading(false); return }
    try {
      const config = { headers: { Authorization: `Bearer ${token}` } }
      const [statsRes, appsRes] = await Promise.allSettled([
        axios.get(`${API_BASE_URL}/dashboard/stats`, config),
        axios.get(`${API_BASE_URL}/dashboard/applied`, config),
      ])
      setData({
        stats: statsRes.status === 'fulfilled' ? statsRes.value.data : null,
        apps:  appsRes.status === 'fulfilled' && Array.isArray(appsRes.value.data) ? appsRes.value.data : [],
      })
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }, [token])

  const handleDelete = useCallback(async (appId) => {
    if (!appId || !token) return
    try {
      await axios.delete(`${API_BASE_URL}/dashboard/applied/${appId}`, { headers: { Authorization: `Bearer ${token}` } })
      fetchData()
    } catch { alert('Failed to delete. Please try again.') }
  }, [token, fetchData])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400 font-bold text-sm uppercase tracking-widest">Loading dashboard...</p>
      </div>
    </div>
  )

  const recentApps = (data.apps || []).slice(0, 5)

  return (
    <div className="space-y-10">
      {/* Stats */}
      {data.stats && <StatsGrid stats={data.stats} />}

      {/* Quick action */}
      <div className="bg-gradient-to-br from-emerald-900/30 to-slate-900 border border-emerald-800/30 rounded-3xl p-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <p className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-2">AI Engine</p>
          <h3 className="text-2xl font-black text-white mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
            Optimize a new resume
          </h3>
          <p className="text-slate-400 text-sm max-w-md">
            Get an instant ATS score and AI-optimized PDF tailored for any job description.
          </p>
        </div>
        <a href="/optimizer"
          className="shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white font-black px-8 py-4 rounded-2xl transition-all shadow-xl shadow-emerald-600/20 text-sm uppercase tracking-widest whitespace-nowrap">
          Start Analysis →
        </a>
      </div>

      {/* Recent applications */}
      <div>
        <div className="flex items-end justify-between mb-5">
          <h2 className="text-2xl font-black text-white flex items-center gap-3"
            style={{ fontFamily: "'Playfair Display', serif" }}>
            <span className="w-1.5 h-7 bg-emerald-500 rounded-full" />
            Recent Applications
          </h2>
          {data.apps.length > 5 && (
            <a href="/applications" className="text-xs font-black text-emerald-400 hover:text-emerald-300 transition-colors">
              View all {data.apps.length} →
            </a>
          )}
        </div>
        <ApplicationsTable applications={recentApps} onDelete={handleDelete} token={token} />
      </div>
    </div>
  )
}


// ── Resume Optimizer page (/optimizer) ────────────────────────────────────────
function OptimizerPage() {
  const [analysisResult, setAnalysisResult] = useState(null)
  const [activeTaskId, setActiveTaskId]     = useState(null)
  const [isAnalyzing, setIsAnalyzing]       = useState(false)
  const token = localStorage.getItem('token')

  useEffect(() => {
    let interval
    if (activeTaskId) {
      setIsAnalyzing(true)
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE_URL}/resume/status/${activeTaskId}`)
          if (res.data.status === 'completed') {
            setAnalysisResult(res.data.result)
            setActiveTaskId(null)
            setIsAnalyzing(false)
            localStorage.setItem('lastTaskId', res.data.result?.task_id || '')
          } else if (res.data.status === 'failed') {
            alert('Analysis failed. Please check your file format.')
            setActiveTaskId(null)
            setIsAnalyzing(false)
          }
        } catch (err) { console.error('Polling error:', err) }
      }, 2000)
    }
    return () => clearInterval(interval)
  }, [activeTaskId])

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <p className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-1">AI Engine</p>
          <h2 className="text-2xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
            Resume Optimizer
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Upload your resume and get an instant ATS score with AI-optimized rewrites.
          </p>
        </div>
        {analysisResult && (
          <button onClick={() => setAnalysisResult(null)}
            className="text-xs font-black text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 px-3 py-2 rounded-xl transition-colors shrink-0">
            + New Analysis
          </button>
        )}
      </div>

      {isAnalyzing ? (
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-16 text-center">
          <div className="w-14 h-14 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-5" />
          <h3 className="text-xl font-black text-white mb-2">AI Engine Processing...</h3>
          <p className="text-slate-400 text-sm">Calculating ATS scores, extracting keywords, generating your optimized PDF.</p>
        </div>
      ) : !analysisResult ? (
        <div className="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden">
          <ResumeUpload onUploadSuccess={(taskId, directResult) => {
            if (directResult) {
              setAnalysisResult(directResult)
              localStorage.setItem('lastTaskId', directResult.task_id || taskId)
            } else {
              setActiveTaskId(taskId)
            }
          }} />
        </div>
      ) : (
        <AtsResultView data={analysisResult} />
      )}
    </div>
  )
}

// ── Settings page (/settings) ─────────────────────────────────────────────────
function SettingsPage() {
  const [profile, setProfile]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [form, setForm]         = useState({ full_name: '', career_track: '', country: '' })
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) { setLoading(false); return }
    axios.get(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        setProfile(r.data)
        setForm({
          full_name:    r.data.full_name || '',
          career_track: r.data.career_track || '',
          country:      r.data.country || '',
        })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [token])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true); setSaved(false)
    try {
      await axios.patch(`${API_BASE_URL}/auth/me`, form, { headers: { Authorization: `Bearer ${token}` } })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save. Please try again.')
    } finally { setSaving(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  )

  const inputCls = 'w-full px-4 py-3 rounded-2xl border-2 border-slate-800 bg-slate-950 outline-none focus:border-emerald-500 transition-all text-white font-semibold text-sm placeholder:text-slate-600'
  const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2'

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <p className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-1">Account</p>
        <h2 className="text-2xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
          Settings
        </h2>
      </div>

      {/* Profile card */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 mb-6">
        <div className="flex items-center gap-4 mb-6 pb-6 border-b border-slate-800">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-lg font-black shadow-lg shadow-emerald-900/40">
            {(profile?.full_name || profile?.email || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0,2)}
          </div>
          <div>
            <p className="text-white font-black text-base">{profile?.full_name || profile?.email?.split('@')[0]}</p>
            <p className="text-slate-500 text-sm">{profile?.email}</p>
            <div className="flex gap-2 mt-1.5">
              {profile?.is_admin && <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/20">ADMIN</span>}
              {profile?.is_hr && !profile?.is_admin && <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/20">HR</span>}
              {!profile?.is_admin && !profile?.is_hr && <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/20">JOB SEEKER</span>}
            </div>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className={labelCls}>Full Name</label>
            <input type="text" className={inputCls} value={form.full_name}
              onChange={e => set('full_name', e.target.value)} placeholder="Your full name" />
          </div>
          <div>
            <label className={labelCls}>Career Track</label>
            <input type="text" className={inputCls} value={form.career_track}
              onChange={e => set('career_track', e.target.value)} placeholder="e.g. DevOps Engineer" />
          </div>
          <div>
            <label className={labelCls}>Country</label>
            <input type="text" className={inputCls} value={form.country}
              onChange={e => set('country', e.target.value)} placeholder="e.g. Nigeria" />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button type="submit" disabled={saving}
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-black px-6 py-3 rounded-2xl text-xs uppercase tracking-widest transition-all disabled:bg-slate-700 disabled:text-slate-500">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
            {saved && <span className="text-emerald-400 text-xs font-bold">✓ Saved successfully</span>}
          </div>
        </form>
      </div>

      {/* Danger zone */}
      <div className="bg-rose-950/20 border border-rose-900/30 rounded-3xl p-6">
        <p className="text-rose-400 font-black text-sm mb-1">Sign Out</p>
        <p className="text-slate-500 text-xs mb-4">You'll need to log in again to access your account.</p>
        <button onClick={() => { localStorage.removeItem('token'); window.location.href = '/login' }}
          className="text-xs font-black px-5 py-2.5 rounded-xl bg-rose-900/40 hover:bg-rose-900/60 text-rose-400 border border-rose-800/40 transition-all uppercase tracking-widest">
          Sign Out of Account
        </button>
      </div>
    </div>
  )
}

// ── Job Feed page (/jobs) ─────────────────────────────────────────────────────
function JobsPage() {
  const [jobs, setJobs]             = useState([])
  const [loading, setLoading]       = useState(true)
  const [countryFilter, setCountry] = useState('')
  const [workType, setWorkType]     = useState('')
  const [search, setSearch]         = useState('')
  const token = localStorage.getItem('token')

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        ...(countryFilter ? { country: countryFilter } : {}),
        ...(search       ? { search }                : {}),
        ...(workType     ? { work_type: workType }   : {}),
      }
      const res = await axios.get(`${API_BASE_URL}/jobs/`, { params })
      setJobs(Array.isArray(res.data) ? res.data : [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }, [countryFilter, workType, search])

  useEffect(() => { fetchJobs() }, [fetchJobs])

  const handleApply = useCallback(async (jobId, jobUrl) => {
    if (!token) { window.location.href = '/login'; return }
    try {
      const res = await axios.post(`${API_BASE_URL}/jobs/${jobId}/apply`, {}, { headers: { Authorization: `Bearer ${token}` } })
      const url = jobUrl || res.data?.job_url
      if (url) window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to apply.')
    }
  }, [token])

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1">
          <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input type="text" placeholder="Search title, company, skill..."
            value={search} onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-3 rounded-2xl border-2 border-slate-800 bg-slate-900 text-sm font-semibold text-white outline-none focus:border-emerald-500 transition-all placeholder:text-slate-600" />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white font-black text-lg">×</button>
          )}
        </div>

        {/* Country */}
        <div className="relative">
          <select value={countryFilter} onChange={e => setCountry(e.target.value)}
            className="pl-4 pr-8 py-3 rounded-2xl border-2 border-slate-800 bg-slate-900 text-sm font-bold text-slate-300 outline-none focus:border-emerald-500 transition-all appearance-none cursor-pointer min-w-[160px]">
            <option value="">🌍 All Countries</option>
            {['Nigeria','Ghana','Kenya','South Africa','United States','United Kingdom','Canada','Germany','France','Netherlands','India','Australia','Singapore','UAE','Brazil','Remote','Worldwide'].map(c => (
              <option key={c} value={c} style={{ background: '#0f172a' }}>{c}</option>
            ))}
          </select>
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none text-xs">▾</span>
        </div>
      </div>

      {/* Work type pills */}
      <div className="flex gap-2 flex-wrap mb-6">
        {[{v:'',l:'🌐 All'},{v:'remote',l:'🌍 Remote'},{v:'hybrid',l:'🏢 Hybrid'},{v:'onsite',l:'📍 On-site'}].map(({v,l}) => (
          <button key={v} onClick={() => setWorkType(v)}
            className={`px-4 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all border-2 ${
              workType === v
                ? 'bg-emerald-600 text-white border-emerald-600 shadow-lg shadow-emerald-600/20'
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-600 hover:text-white'
            }`}>
            {l}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
        </div>
      ) : (
        <JobFeed jobs={jobs} onApply={handleApply} lastTaskId={localStorage.getItem('lastTaskId')} />
      )}
    </div>
  )
}

// ── Landing page (public) ─────────────────────────────────────────────────────
function LandingPage() {
  const LinkedInIcon = () => (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
  return (
    <div className="app-canvas min-h-screen" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="app-canvas-mesh" />
      <div className="app-canvas-grain" />
      <nav className="relative z-10 sticky top-0 z-40 border-b border-slate-800/60 bg-slate-950/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <div>
              <span className="font-black text-white text-base tracking-tight">BAALEBOS CLOUD</span>
              <span className="hidden md:block text-emerald-400 text-[9px] font-bold uppercase tracking-[0.2em] leading-none">AI Talent Infrastructure</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a href="/pricing" className="text-sm font-bold text-slate-400 hover:text-white transition-colors px-4 py-2">Pricing</a>
            <a href="/login"   className="text-sm font-bold text-slate-400 hover:text-white transition-colors px-4 py-2">Login</a>
            <a href="/signup"  className="text-sm font-black text-white bg-emerald-600 hover:bg-emerald-500 px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-emerald-600/20">Get Started →</a>
          </div>
        </div>
      </nav>

      <section className="relative overflow-hidden z-10">
        <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-24">
          <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-12 items-center">

            {/* ── Left: copy + CTAs ── */}
            <div>
              <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-2 mb-6">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-emerald-400 text-xs font-bold uppercase tracking-widest">AI-Powered · Live Jobs Every 6 Hours</span>
              </div>
              <h1 className="text-5xl md:text-6xl font-black text-white leading-[1.05] mb-6"
                style={{ fontFamily: "'Playfair Display', serif" }}>
                Get Hired at<br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-blue-400 to-purple-400">Top Tech Companies</span><br/>
                Worldwide.
              </h1>
              <p className="text-slate-400 text-lg leading-relaxed mb-8 max-w-xl">
                Upload your resume, get an instant ATS score, and receive an AI-optimized PDF designed to pass every filter — from Nigeria to Silicon Valley.
              </p>
              <div className="flex flex-wrap gap-4 mb-12">
                <a href="/signup" className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-black px-8 py-4 rounded-2xl transition-all shadow-xl shadow-emerald-600/25 text-sm uppercase tracking-widest active:scale-[0.98]">
                  Start Free →
                </a>
                <a href="/pricing" className="inline-flex items-center gap-2 border-2 border-slate-700 hover:border-emerald-500/50 text-slate-300 hover:text-white font-bold px-8 py-4 rounded-2xl transition-all text-sm">
                  View Pricing
                </a>
              </div>
              <div className="flex flex-wrap gap-8">
                {[['94%','Avg ATS Score'],['6 hrs','Job Refresh Rate'],['80+','Countries Covered'],['Free','Always']].map(([v,l]) => (
                  <div key={l}><div className="text-2xl font-black text-white">{v}</div><div className="text-xs text-slate-500 font-semibold mt-0.5">{l}</div></div>
                ))}
              </div>
            </div>

            {/* ── Right: live visual — fills the dead space, doubles as social proof ── */}
            <div className="relative hidden lg:block">
              <div className="absolute -inset-8 bg-gradient-to-br from-emerald-500/10 via-transparent to-blue-500/10 rounded-[3rem] blur-2xl" />

              {/* ATS score card */}
              <div className="relative bg-slate-900/90 backdrop-blur border border-slate-800 rounded-3xl p-6 shadow-2xl mb-4 ml-auto max-w-sm">
                <div className="flex items-center gap-2 mb-4">
                  <span className="w-3 h-3 rounded-full bg-rose-500"/>
                  <span className="w-3 h-3 rounded-full bg-amber-500"/>
                  <span className="w-3 h-3 rounded-full bg-emerald-500"/>
                  <span className="text-slate-500 text-xs font-mono ml-2">ats_result.json</span>
                </div>
                <div className="text-xs font-mono space-y-1">
                  <div className="text-slate-400">{'{'}</div>
                  <div className="pl-4"><span className="text-blue-400">"ats_score"</span><span className="text-slate-500">: </span><span className="text-emerald-400">94</span><span className="text-slate-500">,</span></div>
                  <div className="pl-4"><span className="text-blue-400">"keywords_matched"</span><span className="text-slate-500">: </span><span className="text-emerald-400">28/30</span><span className="text-slate-500">,</span></div>
                  <div className="pl-4"><span className="text-blue-400">"status"</span><span className="text-slate-500">: </span><span className="text-amber-400">"interview_ready"</span></div>
                  <div className="text-slate-400">{'}'}</div>
                </div>
              </div>

              {/* Match engine card */}
              <div className="relative bg-slate-900/90 backdrop-blur border border-blue-500/20 rounded-3xl p-6 shadow-2xl mr-8 max-w-xs">
                <div className="text-slate-500 text-xs font-mono mb-3">// AI Match Engine</div>
                <div className="text-xs font-mono space-y-1 mb-4">
                  <div><span className="text-purple-400">const</span> <span className="text-blue-300">match</span> <span className="text-slate-500">= </span><span className="text-emerald-400">97.3</span><span className="text-slate-500">%</span></div>
                  <div><span className="text-purple-400">const</span> <span className="text-blue-300">role</span> <span className="text-slate-500">= </span><span className="text-amber-400">"DevOps Eng."</span></div>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full w-[97%] bg-gradient-to-r from-emerald-500 to-blue-400 rounded-full" />
                </div>
              </div>

              {/* Floating badge */}
              <div className="absolute -top-6 -right-4 bg-emerald-500 text-white text-xs font-black px-4 py-2 rounded-full shadow-xl shadow-emerald-500/30 rotate-3">
                ✓ Live scoring
              </div>
            </div>

          </div>
        </div>
      </section>

      <footer className="relative z-10 max-w-7xl mx-auto px-4 md:px-8 py-12 border-t border-slate-800 mt-20 flex flex-col md:flex-row items-center justify-between gap-6">
        <p className="text-slate-600 text-sm">© {new Date().getFullYear()} Baalebos Cloud · AI Talent Infrastructure</p>
        <div className="flex gap-4">
          <a href="https://www.linkedin.com/in/oluwadare-jayeola-6874591b4/" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0A66C2] hover:bg-[#004182] text-white font-bold text-sm transition-all">
            <LinkedInIcon /> LinkedIn
          </a>
          <a href="https://github.com/baalebos-cloud" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-sm border border-slate-700 transition-all">
            GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}


// ── Applications page (/applications) ────────────────────────────────────────
function ApplicationsPage() {
  const [apps, setApps]     = useState([])
  const [loading, setLoading] = useState(true)
  const token = localStorage.getItem('token')

  const fetchApps = useCallback(async () => {
    if (!token) { setLoading(false); return }
    try {
      const res = await axios.get(`${API_BASE_URL}/dashboard/applied`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setApps(Array.isArray(res.data) ? res.data : [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }, [token])

  useEffect(() => { fetchApps() }, [fetchApps])

  const handleDelete = useCallback(async (appId) => {
    if (!appId || !token) return
    try {
      await axios.delete(`${API_BASE_URL}/dashboard/applied/${appId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchApps()
    } catch { alert('Failed to delete. Please try again.') }
  }, [token, fetchApps])

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  )

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <p className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-1">Tracker</p>
          <h2 className="text-2xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
            Your Applications
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            <span className="text-emerald-400 font-black">{apps.length}</span> job{apps.length !== 1 ? 's' : ''} tracked
          </p>
        </div>
        <a href="/jobs"
          className="text-xs font-black px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white transition-all uppercase tracking-widest">
          Browse Jobs →
        </a>
      </div>
      <ApplicationsTable applications={apps} onDelete={handleDelete} token={token} />
    </div>
  )
}

// ── App router ────────────────────────────────────────────────────────────────
function App() {
  const token = localStorage.getItem('token')

  // Capture ?ref= referral code and ?upgraded= Stripe success redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const ref = params.get('ref')
    if (ref) localStorage.setItem('ref_code', ref)
    if (params.get('upgraded') === 'true') {
      alert('Welcome to Pro! Your account has been upgraded.')
      window.history.replaceState({}, '', '/')
    }
  }, [])

  return (
    <Router>
      <Routes>
        {/* ── Public landing ── */}
        <Route path="/landing" element={<LandingPage />} />

        {/* ── Auth pages (no layout) ── */}
        <Route path="/signup"          element={<Signup />} />
        <Route path="/login"           element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password"  element={<ResetPassword />} />
        <Route path="/verify-email"    element={<VerifyEmail />} />
        <Route path="/hr/login"        element={<HRLogin />} />
        <Route path="/hr/signup"       element={<HRSignup />} />
        <Route path="/hr/verify"       element={<VerifyEmail />} />

        {/* ── Authenticated routes — wrapped in DashboardLayout ── */}
        <Route path="/" element={
          token
            ? <DashboardLayout><OverviewPage /></DashboardLayout>
            : <LandingPage />
        } />
        <Route path="/optimizer" element={
          <RequireAuth><DashboardLayout><OptimizerPage /></DashboardLayout></RequireAuth>
        } />
        <Route path="/jobs" element={
          <RequireAuth><DashboardLayout><JobsPage /></DashboardLayout></RequireAuth>
        } />
        <Route path="/applications" element={
          <RequireAuth><DashboardLayout><ApplicationsPage /></DashboardLayout></RequireAuth>
        } />
        <Route path="/referral" element={
          <RequireAuth><DashboardLayout><ReferralDashboard /></DashboardLayout></RequireAuth>
        } />
        <Route path="/profile" element={
          <RequireAuth><DashboardLayout><ProfilePage /></DashboardLayout></RequireAuth>
        } />
        <Route path="/settings" element={
          <RequireAuth><DashboardLayout><SettingsPage /></DashboardLayout></RequireAuth>
        } />
        <Route path="/pricing" element={
          <DashboardLayout><PricingPage /></DashboardLayout>
        } />
        <Route path="/admin" element={
          <RequireRole role="admin"><DashboardLayout><AdminDashboard /></DashboardLayout></RequireRole>
        } />
        <Route path="/hr" element={
          <RequireRole role="hr"><DashboardLayout><HRPortal /></DashboardLayout></RequireRole>
        } />

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  )
}

export default App
