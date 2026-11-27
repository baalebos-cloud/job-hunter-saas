import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import axios from 'axios'

import DashboardLayout from './components/layout/DashboardLayout'
import GovernanceDashboard from './components/governance/GovernanceDashboard'
import TalentOverview from './components/TalentOverview'
import ApplicationsTable from './components/dashboard/ApplicationsTable'
import JobBoard from './components/jobs/JobBoard'
import ApplyPage from './components/jobs/ApplyPage'
import ResumeUpload from './components/dashboard/ResumeUpload'
import AtsResultView from './components/dashboard/AtsResultView'
import HelpPage from './components/support/HelpPage'
import MyResumes from './components/resumes/MyResumes'
import BulkTailor from './components/dashboard/BulkTailor'
import UnsubscribePage from './components/support/UnsubscribePage'
import { signOut, errorText } from './lib/session'
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
import TeamJoin from './components/team/TeamJoin'
import StaffInvite from './components/team/StaffInvite'
import AboutPage from './components/site/AboutPage'
import ContactPage from './components/site/ContactPage'
import LegalPage from './components/site/LegalPage'
import LandingPage from './components/site/LandingPage'
import { captureFirstTouch } from './lib/attribution'
import TeamSettings from './components/team/TeamSettings'
import ApiKeys from './components/developers/ApiKeys'
import ApiDocs from './components/developers/ApiDocs'
import BrandingSettings from './components/branding/BrandingSettings'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// ── Auth guard — redirect to login if no token ────────────────────────────────
function RequireAuth({ children }) {
  const location = useLocation()
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return children
}

// ── Role guard — blocks non-admin/HR users from restricted pages ─────────────
// FIX 3: Admin and HR pages are hidden from regular users, even via direct URL
function RequireRole({ role, children }) {
  const location = useLocation()
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

  if (!token) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  )

  const GOVERNANCE = ['metrics:read', 'audit:read', 'users:read', 'reports:read']
  const CONSOLE = ['admin:access', 'analytics:read', 'growth:read', 'campaigns:read', 'content:read', 'support:manage', 'users:manage_roles', 'legal:manage']
  const hasAccess = role === 'admin' ? (profile?.is_admin || (profile?.permissions || []).some(p => CONSOLE.includes(p)))
    : role === 'governance' ? (profile?.permissions || []).some(p => GOVERNANCE.includes(p))
    : (profile?.is_admin || profile?.is_hr)
  if (!hasAccess) return <Navigate to="/" replace />

  return children
}

function GovernancePage() {
  const [permissions, setPermissions] = useState(null)
  useEffect(() => {
    axios.get(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
      .then(r => setPermissions(r.data.permissions || [])).catch(() => setPermissions([]))
  }, [])
  if (!permissions) return <p role="status">Loading…</p>
  return <GovernanceDashboard permissions={permissions} />
}

// ── Overview page (/) ─────────────────────────────────────────────────────────
function OverviewPage() { return <TalentOverview /> }

// ── Resume Optimizer page (/optimizer) ────────────────────────────────────────
const RESUME_STEPS = ['Your resume', 'Target job', 'Match review', 'Preview & download']

function ResumeStepper({ step }) {
  return (
    <ol className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm mb-6" aria-label="Resume steps">
      {RESUME_STEPS.map((label, index) => {
        const n = index + 1, done = n < step, current = n === step
        return (
          <li key={label} className="flex items-center gap-2 min-w-0 flex-1 last:flex-none" aria-current={current ? 'step' : undefined}>
            <span className={`w-6 h-6 shrink-0 rounded-full grid place-items-center text-xs font-semibold ${done ? 'bg-emerald-600 text-white' : current ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-600'}`}>{done ? '✓' : n}</span>
            <span className={`hidden sm:inline truncate ${done ? 'text-emerald-700 font-medium' : current ? 'font-semibold text-slate-900' : 'text-slate-500'}`}>{label}</span>
            {n < RESUME_STEPS.length && <span className={`flex-1 h-px min-w-[12px] ${done ? 'bg-emerald-300' : 'bg-slate-200'}`} />}
          </li>
        )
      })}
    </ol>
  )
}

function OptimizerPage() {
  const [analysisResult, setAnalysisResult] = useState(null)
  const [activeTaskId, setActiveTaskId]     = useState(null)
  const [isAnalyzing, setIsAnalyzing]       = useState(false)
  const [failure, setFailure]               = useState('')
  const jobId = new URLSearchParams(window.location.search).get('job')
  const token = localStorage.getItem('token')
  const [enterprise, setEnterprise] = useState(false)   // bulk tailoring is an Enterprise feature
  const [mode, setMode] = useState('single')
  useEffect(() => {
    axios.get(`${API_BASE_URL}/billing/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setEnterprise(r.data?.plan === 'enterprise')).catch(() => {})
  }, [token])

  useEffect(() => {
    let interval
    if (activeTaskId) {
      setIsAnalyzing(true)
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE_URL}/resume/status/${activeTaskId}`, { headers: { Authorization: `Bearer ${token}` } })
          if (res.data.status === 'completed') {
            setAnalysisResult(res.data.result)
            setActiveTaskId(null)
            setIsAnalyzing(false)
            localStorage.setItem('lastTaskId', res.data.result?.task_id || res.data.task_id || activeTaskId)
          } else if (res.data.status === 'failed') {
            setFailure(res.data.error || 'Analysis failed. Please retry.')
            setActiveTaskId(null)
            setIsAnalyzing(false)
          }
        } catch { /* keep polling; transient network errors are expected */ }
      }, 2000)
    }
    return () => clearInterval(interval)
  }, [activeTaskId, token])

  const step = analysisResult ? 4 : isAnalyzing ? 3 : 1
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Tailor your resume to a job</h2>
          <p className="text-slate-500 text-sm mt-1">We match your resume to the job description, rewrite it around the role using only your real experience, and show you the result before you download.</p>
        </div>
        {analysisResult && (
          <button type="button" onClick={() => { setAnalysisResult(null); setFailure('') }}
            className="text-sm font-semibold rounded-xl px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50">Tailor for another job</button>
        )}
      </div>
      {enterprise && !analysisResult && !isAnalyzing && (
        <div className="mb-5 inline-flex rounded-xl border border-slate-200 bg-white p-1" role="tablist" aria-label="Tailoring mode">
          {[['single', 'One job'], ['bulk', 'Several jobs (up to 10)']].map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={mode === id} onClick={() => setMode(id)}
              className={`px-3.5 py-1.5 text-sm font-medium rounded-lg ${mode === id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:text-slate-900'}`}>{label}</button>))}
        </div>)}
      {enterprise && mode === 'bulk' && !analysisResult && !isAnalyzing ? <BulkTailor /> : (<>
      <ResumeStepper step={step} />
      {failure && <p role="alert" className="mb-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-700">{failure}</p>}
      {isAnalyzing ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center" role="status">
          <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-5" />
          <h3 className="text-lg font-semibold text-slate-900 mb-1">Matching your resume to the job…</h3>
          <p className="text-slate-500 text-sm">Reading the requirements, tailoring your resume and building the PDF. This can take a minute or two. Keep this page open.</p>
        </div>
      ) : !analysisResult ? (
        <ResumeUpload onUploadSuccess={(taskId, directResult) => {
          setFailure('')
          if (directResult) {
            setAnalysisResult(directResult)
            localStorage.setItem('lastTaskId', directResult.task_id || taskId)
          } else {
            setActiveTaskId(taskId)
          }
        }} />
      ) : (
        <AtsResultView data={analysisResult} jobId={jobId} />
      )}
      </>)}
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
      alert(errorText(err, 'Failed to save. Please try again.'))
    } finally { setSaving(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  )

  const inputCls = 'w-full px-4 py-3 rounded-2xl border-2 border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 transition-all text-slate-900 font-semibold text-sm placeholder:text-slate-600'
  const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-500 mb-2'

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <p className="text-xs font-black uppercase tracking-widest text-emerald-400 mb-1">Account</p>
        <h2 className="text-2xl font-black text-slate-900" style={{ fontFamily: "'Playfair Display', serif" }}>
          Settings
        </h2>
      </div>

      {/* Profile card */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 mb-6">
        <div className="flex items-center gap-4 mb-6 pb-6 border-b border-slate-200">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-slate-900 text-lg font-black shadow-lg shadow-emerald-900/40">
            {(profile?.full_name || profile?.email || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0,2)}
          </div>
          <div>
            <p className="text-slate-900 font-black text-base">{profile?.full_name || profile?.email?.split('@')[0]}</p>
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
              className="bg-emerald-600 hover:bg-emerald-500 text-slate-900 font-black px-6 py-3 rounded-2xl text-xs uppercase tracking-widest transition-all disabled:bg-slate-700 disabled:text-slate-500">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
            {saved && <span className="text-emerald-400 text-xs font-bold">✓ Saved successfully</span>}
          </div>
        </form>
      </div>

      <TeamSettings />
      <ApiKeys />
      <BrandingSettings />

      {/* Danger zone */}
      <div className="bg-rose-950/20 border border-rose-900/30 rounded-3xl p-6">
        <p className="text-rose-400 font-black text-sm mb-1">Sign Out</p>
        <p className="text-slate-500 text-xs mb-4">You'll need to log in again to access your account.</p>
        <button onClick={() => signOut(axios)}
          className="text-xs font-black px-5 py-2.5 rounded-xl bg-rose-900/40 hover:bg-rose-900/60 text-rose-400 border border-rose-800/40 transition-all uppercase tracking-widest">
          Sign Out of Account
        </button>
      </div>
    </div>
  )
}

// ── Job board page (/jobs) ────────────────────────────────────────────────────
function JobsPage() {
  const token = localStorage.getItem('token')
  const handleApply = useCallback(async (jobId, jobUrl, resumeId) => {
    if (!token) { window.location.href = '/login'; return }
    const res = await axios.post(`${API_BASE_URL}/jobs/${jobId}/apply`, { resume_id: resumeId || null },
      { headers: { Authorization: `Bearer ${token}` } })
    return res.data
  }, [token])
  return <JobBoard onApply={handleApply} />
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
          <p className="text-xs font-black uppercase tracking-widest text-emerald-700 mb-1">Tracker</p>
          <h2 className="text-2xl font-black text-slate-900" style={{ fontFamily: "'Playfair Display', serif" }}>
            Your Applications
          </h2>
          <p className="text-slate-600 text-sm mt-1">
            <span className="text-emerald-700 font-black">{apps.length}</span> job{apps.length !== 1 ? 's' : ''} tracked
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
    captureFirstTouch()
    if (params.get('upgraded') === 'true') {
      alert('Welcome to Pro! Your account has been upgraded.')
      window.history.replaceState({}, '', '/')
    }
  }, [])

  return (
    <HelmetProvider>
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
        <Route path="/unsubscribe"     element={<UnsubscribePage />} />
        <Route path="/team/join"       element={<TeamJoin />} />
        <Route path="/staff-invite"    element={<StaffInvite />} />
        <Route path="/about"           element={<AboutPage />} />
        <Route path="/contact"         element={<ContactPage />} />
        <Route path="/legal/:slug"     element={<LegalPage />} />
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
        <Route path="/resumes" element={
          <RequireAuth><DashboardLayout><MyResumes /></DashboardLayout></RequireAuth>
        } />
        <Route path="/jobs" element={
          <RequireAuth><DashboardLayout><JobsPage /></DashboardLayout></RequireAuth>
        } />
        <Route path="/apply/:jobId" element={
          <RequireAuth><DashboardLayout><ApplyPage /></DashboardLayout></RequireAuth>
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
        <Route path="/developers" element={
          <DashboardLayout><ApiDocs /></DashboardLayout>
        } />
        <Route path="/help" element={
          <DashboardLayout><HelpPage /></DashboardLayout>
        } />
        <Route path="/pricing" element={
          <DashboardLayout><PricingPage /></DashboardLayout>
        } />
        <Route path="/admin" element={
          <RequireRole role="admin"><DashboardLayout><AdminDashboard /></DashboardLayout></RequireRole>
        } />
        <Route path="/governance" element={
          <RequireRole role="governance"><DashboardLayout><GovernancePage /></DashboardLayout></RequireRole>
        } />
        <Route path="/hr" element={
          <RequireRole role="hr"><DashboardLayout><HRPortal /></DashboardLayout></RequireRole>
        } />

          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Router>
    </HelmetProvider>
  )
}

export default App
