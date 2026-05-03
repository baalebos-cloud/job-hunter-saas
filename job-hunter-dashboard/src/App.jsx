import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'

import StatsGrid from './components/StatsGrid'
import ApplicationsTable from './components/dashboard/ApplicationsTable'
import JobFeed from './components/JobFeed'
import ResumeUpload from './components/dashboard/ResumeUpload'
import AtsResultView from './components/dashboard/AtsResultView'
import Signup from './components/auth/Signup'
import Login from './components/auth/Login'
import AdminDashboard from './components/admin/AdminDashboard'
import HRPortal from './components/hr/HRPortal'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// ── LinkedIn / GitHub SVGs ────────────────────────────────────────────────────
const LinkedInIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
  </svg>
)
const GitHubIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
  </svg>
)

const Dashboard = () => {
  const [data, setData] = useState({ stats: null, apps: [], availableJobs: [] })
  const [loading, setLoading] = useState(true)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [activeTaskId, setActiveTaskId] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [countryFilter, setCountryFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [workTypeFilter, setWorkTypeFilter] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const token = localStorage.getItem('token')
  const isAuthenticated = !!token

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token')
    window.location.href = '/login'
  }, [])

  const fetchData = useCallback(async () => {
    try {
      const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {}
      const params = {
        ...(countryFilter ? { country: countryFilter } : {}),
        ...(searchQuery ? { search: searchQuery } : {}),
        ...(workTypeFilter ? { work_type: workTypeFilter } : {}),
      }
      const requests = [axios.get(`${API_BASE_URL}/jobs/`, { params })]
      if (token) {
        requests.push(axios.get(`${API_BASE_URL}/dashboard/stats`, config))
        requests.push(axios.get(`${API_BASE_URL}/dashboard/applied`, config))
      }
      const results = await Promise.allSettled(requests)
      setData({
        availableJobs: results[0].status === 'fulfilled' && Array.isArray(results[0].value.data) ? results[0].value.data : [],
        stats: token && results[1]?.status === 'fulfilled' ? results[1].value.data : null,
        apps: token && results[2]?.status === 'fulfilled' && Array.isArray(results[2].value.data) ? results[2].value.data : [],
      })
    } catch (err) {
      console.error('Fetch error:', err)
    } finally {
      setLoading(false)
    }
  }, [token, countryFilter, searchQuery, workTypeFilter])

  const handleDelete = useCallback(async (appId) => {
    if (!appId || !token) return
    try {
      await axios.delete(`${API_BASE_URL}/dashboard/applied/${appId}`, { headers: { Authorization: `Bearer ${token}` } })
      fetchData()
    } catch { alert('Failed to delete. Please try again.') }
  }, [token, fetchData])

  const handleApply = useCallback(async (jobId, jobUrl) => {
    if (!token) { alert('Please login to apply.'); window.location.href = '/login'; return }
    try {
      const res = await axios.post(`${API_BASE_URL}/jobs/${jobId}/apply`, {}, { headers: { Authorization: `Bearer ${token}` } })
      fetchData()
      // Open the original job source URL in a new tab if available
      const url = jobUrl || res.data?.job_url
      if (url) window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to apply. Please try again.')
    }
  }, [token, fetchData])

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
            localStorage.setItem('lastTaskId', res.data.result?.task_id || res.data.result?.resume_id || '')
            fetchData()
          } else if (res.data.status === 'failed') {
            alert('Analysis failed. Please check your file format.')
            setActiveTaskId(null)
            setIsAnalyzing(false)
          }
        } catch (err) { console.error('Polling error:', err) }
      }, 2000)
    }
    return () => clearInterval(interval)
  }, [activeTaskId, fetchData])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400 font-bold text-sm uppercase tracking-widest">Connecting to AI Engine...</p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-950" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* ── NAVBAR ── */}
      <nav className="sticky top-0 z-40 border-b border-slate-800/60 bg-slate-950/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <div>
              <span className="font-black text-white text-base tracking-tight">BAALEBOS CLOUD</span>
              <span className="hidden md:block text-emerald-400 text-[9px] font-bold uppercase tracking-[0.2em] leading-none">AI Talent Infrastructure</span>
            </div>
          </a>

          <div className="flex items-center gap-3">
            {!isAuthenticated ? (
              <>
                <a href="/login" className="text-sm font-bold text-slate-400 hover:text-white transition-colors px-4 py-2">Login</a>
                <a href="/signup" className="text-sm font-black text-white bg-emerald-600 hover:bg-emerald-500 px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-emerald-600/20">
                  Get Started →
                </a>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <button onClick={handleLogout}
                  className="text-sm font-bold text-slate-400 hover:text-rose-400 border border-slate-800 hover:border-rose-500/30 px-4 py-2 rounded-xl transition-all">
                  Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* ── HERO SECTION ── */}
      <section className="relative overflow-hidden">
        {/* Tech background image */}
        <img
          src="https://images.unsplash.com/photo-1518770660439-4636190af475?w=1600&q=80"
          alt="tech background"
          className="absolute inset-0 w-full h-full object-cover opacity-[0.07]"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/60 via-slate-950/80 to-slate-950" />

        {/* Animated grid */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: 'linear-gradient(#10b981 1px, transparent 1px), linear-gradient(90deg, #10b981 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-16">
          <div className="max-w-3xl">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-2 mb-6">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-emerald-400 text-xs font-bold uppercase tracking-widest">AI-Powered · Live Jobs Every 5 Minutes</span>
            </div>

            <h1 className="text-5xl md:text-6xl font-black text-white leading-[1.05] mb-6"
              style={{ fontFamily: "'Playfair Display', serif" }}>
              Get Hired at<br/>
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-blue-400 to-purple-400">
                Top Tech Companies
              </span><br/>
              Worldwide.
            </h1>

            <p className="text-slate-400 text-lg leading-relaxed mb-8 max-w-xl">
              Upload your resume, get an instant ATS score, and receive an AI-optimized PDF designed to pass every filter — from Nigeria to Silicon Valley.
            </p>

            <div className="flex flex-wrap gap-4 mb-12">
              {!isAuthenticated ? (
                <>
                  <a href="/signup"
                    className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-black px-8 py-4 rounded-2xl transition-all shadow-xl shadow-emerald-600/25 text-sm uppercase tracking-widest active:scale-[0.98]">
                    Start Free →
                  </a>
                  <a href="/login"
                    className="inline-flex items-center gap-2 border-2 border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white font-bold px-8 py-4 rounded-2xl transition-all text-sm">
                    Sign In
                  </a>
                </>
              ) : (
                <button onClick={() => document.getElementById('optimizer')?.scrollIntoView({ behavior: 'smooth' })}
                  className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-black px-8 py-4 rounded-2xl transition-all shadow-xl shadow-emerald-600/25 text-sm uppercase tracking-widest">
                  Optimize My Resume →
                </button>
              )}
            </div>

            {/* Stats row */}
            <div className="flex flex-wrap gap-8">
              {[['94%', 'Avg ATS Score'], ['5 min', 'Job Refresh Rate'], ['80+', 'Countries Covered'], ['Free', 'Always']].map(([v, l]) => (
                <div key={l}>
                  <div className="text-2xl font-black text-white">{v}</div>
                  <div className="text-xs text-slate-500 font-semibold mt-0.5">{l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-4 md:px-8 pb-24 space-y-20">

        {/* ── AI RESUME OPTIMIZER ── */}
        <section id="optimizer">
          <div className="flex items-end justify-between mb-6">
            <div>
              <div className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-2">Step 1</div>
              <h2 className="text-3xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
                AI Resume Optimizer
              </h2>
              <p className="text-slate-400 font-medium mt-1">Upload your resume and get an interview-ready PDF in minutes.</p>
            </div>
            {analysisResult && (
              <button onClick={() => setAnalysisResult(null)}
                className="text-emerald-400 text-sm font-black uppercase tracking-widest hover:text-emerald-300 transition-colors border border-emerald-500/20 px-4 py-2 rounded-xl">
                + New Analysis
              </button>
            )}
          </div>

          {isAnalyzing ? (
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-16 text-center">
              <div className="w-16 h-16 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-6" />
              <h3 className="text-xl font-black text-white mb-2">AI Engine Processing...</h3>
              <p className="text-slate-400 font-medium">Calculating ATS scores, extracting keywords, generating your optimized PDF.</p>
              <div className="flex justify-center gap-6 mt-8">
                {['Parsing Resume', 'Scoring Keywords', 'Generating PDF'].map((s, i) => (
                  <div key={s} className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${i === 0 ? 'bg-emerald-400 animate-pulse' : 'bg-slate-700'}`} />
                    <span className="text-xs font-bold text-slate-500">{s}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : !analysisResult ? (
            <div className="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden">
              <ResumeUpload onUploadSuccess={(taskId, directResult) => {
                if (directResult) {
                  // Railway mode: result returned directly, no polling needed
                  setAnalysisResult(directResult);
                  localStorage.setItem('lastTaskId', directResult.task_id || taskId);
                  fetchData();
                } else {
                  // Local dev mode: poll for result
                  setActiveTaskId(taskId);
                }
              }} />
            </div>
          ) : (
            <AtsResultView data={analysisResult} />
          )}
        </section>

        {/* ── DASHBOARD STATS + TRACKER (authenticated) ── */}
        {isAuthenticated ? (
          <section>
            <div className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-2">Your Dashboard</div>
            <h2 className="text-3xl font-black text-white mb-8" style={{ fontFamily: "'Playfair Display', serif" }}>
              Application Overview
            </h2>
            {data.stats && <div className="mb-8"><StatsGrid stats={data.stats} /></div>}
            <div>
              <h3 className="text-xl font-black text-white mb-4 flex items-center gap-3">
                <span className="w-1.5 h-6 bg-emerald-500 rounded-full" />
                Application Tracker
              </h3>
              <ApplicationsTable applications={data.apps || []} onDelete={handleDelete} token={token} />
            </div>
          </section>
        ) : (
          <section className="relative overflow-hidden rounded-3xl">
            <img src="https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1200&q=80"
              alt="tech" className="absolute inset-0 w-full h-full object-cover opacity-10" />
            <div className="absolute inset-0 bg-gradient-to-r from-slate-900 to-slate-900/80" />
            <div className="relative z-10 p-12 flex flex-col md:flex-row items-center justify-between gap-8">
              <div>
                <h3 className="text-2xl font-black text-white mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>
                  Track Every Application
                </h3>
                <p className="text-slate-400 font-medium max-w-md">
                  Create a free account to save your ATS scores, track applications, message HR directly, and download your optimized resume.
                </p>
              </div>
              <a href="/signup"
                className="shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white font-black px-8 py-4 rounded-2xl transition-all shadow-xl shadow-emerald-600/20 text-sm uppercase tracking-widest whitespace-nowrap">
                Join Free →
              </a>
            </div>
          </section>
        )}

        {/* ── GLOBAL JOB FEED ── */}
        <section>
          <div className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-2">Live · Updates Every 5 Minutes</div>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
            <h2 className="text-3xl font-black text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
              Global Tech Jobs
            </h2>
            {/* Country filter */}
            <div className="relative">
              <select value={countryFilter} onChange={e => setCountryFilter(e.target.value)}
                className="pl-4 pr-10 py-3 rounded-2xl border-2 border-slate-800 bg-slate-900 text-sm font-bold text-slate-300 outline-none focus:border-emerald-500 transition-all appearance-none cursor-pointer"
                style={{ color: countryFilter ? '#fff' : '#94a3b8' }}>
                <option value="">🌍 All Countries</option>
                {['Nigeria','Ghana','Kenya','South Africa','United States','United Kingdom','Canada','Germany','France','Netherlands','India','Australia','Singapore','UAE','Brazil','Remote','Worldwide'].map(c => (
                  <option key={c} value={c} style={{ background: '#0f172a' }}>{c}</option>
                ))}
              </select>
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none text-xs">▾</span>
            </div>
          </div>

          {/* Work type pills */}
          <div className="flex gap-2 flex-wrap mb-4">
            {[{v:'',l:'🌐 All'},{v:'remote',l:'🌍 Remote'},{v:'hybrid',l:'🏢 Hybrid'},{v:'onsite',l:'📍 On-site'}].map(({v,l}) => (
              <button key={v} onClick={() => setWorkTypeFilter(v)}
                className={`px-4 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all border-2 ${
                  workTypeFilter === v
                    ? 'bg-emerald-600 text-white border-emerald-600 shadow-lg shadow-emerald-600/20'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-600 hover:text-white'
                }`}>
                {l}
              </button>
            ))}
          </div>

          {/* Search bar */}
          <div className="relative mb-4">
            <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input type="text"
              placeholder="Search by title, company, skill... e.g. React Developer, AWS, Nigeria"
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-10 py-4 rounded-2xl border-2 border-slate-800 bg-slate-900 text-sm font-semibold text-white outline-none focus:border-emerald-500 transition-all placeholder:text-slate-600" />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white font-black text-xl transition-colors">×</button>
            )}
          </div>

          {(searchQuery || countryFilter || workTypeFilter) && (
            <p className="text-xs font-bold text-slate-500 mb-4">
              <span className="text-emerald-400">{data.availableJobs?.length || 0}</span> job{data.availableJobs?.length !== 1 ? 's' : ''} found
              {searchQuery && <span> for "<span className="text-white">{searchQuery}</span>"</span>}
              {countryFilter && <span> in <span className="text-white">{countryFilter}</span></span>}
              {workTypeFilter && <span> · <span className="text-white capitalize">{workTypeFilter}</span></span>}
            </p>
          )}

          <JobFeed jobs={data.availableJobs || []} onApply={handleApply}
            lastTaskId={activeTaskId || localStorage.getItem('lastTaskId')} />
        </section>

        {/* ── FOOTER ── */}
        <footer className="border-t border-slate-800 pt-12">
          <div className="flex flex-col md:flex-row items-center justify-between gap-8">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
                  </svg>
                </div>
                <span className="font-black text-white text-lg tracking-tight">BAALEBOS CLOUD</span>
              </div>
              <p className="text-slate-500 text-sm font-medium max-w-xs">
                DevOps & Cloud Engineer · Building production-ready AI systems for global engineers.
              </p>
            </div>

            <div className="flex items-center gap-4">
              <a href="https://www.linkedin.com/in/oluwadare-jayeola-6874591b4/"
                target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-[#0A66C2] hover:bg-[#004182] text-white font-bold text-sm transition-all shadow-lg shadow-blue-900/20 hover:scale-105 active:scale-100">
                <LinkedInIcon /> LinkedIn
              </a>
              <a href="https://github.com/baalebos-cloud"
                target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-sm transition-all shadow-lg hover:scale-105 active:scale-100 border border-slate-700">
                <GitHubIcon /> GitHub
              </a>
            </div>
          </div>

          <p className="text-center text-xs text-slate-700 font-medium mt-10">
            © {new Date().getFullYear()} Baalebos Cloud · AI Talent Infrastructure · Built for global engineers
          </p>
        </footer>
      </div>
    </div>
  )
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/hr" element={<HRPortal />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  )
}

export default App
