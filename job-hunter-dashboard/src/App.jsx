import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'

// Dashboard Components
import StatsGrid from './components/StatsGrid'
import ApplicationsTable from './components/dashboard/ApplicationsTable'
import JobFeed from './components/JobFeed'
import ResumeUpload from './components/dashboard/ResumeUpload'
import AtsResultView from './components/dashboard/AtsResultView'
import Signup from './components/auth/Signup'
import Login from './components/auth/Login'

// --- DASHBOARD COMPONENT ---
const Dashboard = () => {
  const [data, setData] = useState({ stats: null, apps: [], availableJobs: [] })
  const [loading, setLoading] = useState(true)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [activeTaskId, setActiveTaskId] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  // Track login state for the header
  const isAuthenticated = !!localStorage.getItem("token");

  const handleLogout = () => {
    localStorage.removeItem("token");
    window.location.reload(); // Refresh to clear state
  };

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, appsRes, jobsRes] = await Promise.all([
        axios.get('http://127.0.0.1:8000/dashboard/stats'),
        axios.get('http://127.0.0.1:8000/dashboard/applied'),
        axios.get('http://127.0.0.1:8000/jobs/')
      ])
      setData({ stats: statsRes.data, apps: appsRes.data, availableJobs: jobsRes.data })
    } catch (err) {
      console.error("API Error:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    let interval;
    if (activeTaskId) {
      setIsAnalyzing(true);
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`http://127.0.0.1:8000/resume/status/${activeTaskId}`);
          if (res.data.status === "completed") {
            setAnalysisResult(res.data.result);
            setActiveTaskId(null);
            setIsAnalyzing(false);
            fetchData();
          } else if (res.data.status === "failed") {
            alert("Analysis failed");
            setActiveTaskId(null);
            setIsAnalyzing(false);
          }
        } catch (err) { console.error("Polling error:", err); }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [activeTaskId, fetchData]);

  const handleWithdraw = async (appId) => {
    if (window.confirm("Withdraw this application?")) {
      try {
        await axios.delete(`http://127.0.0.1:8000/application/${appId}`)
        fetchData()
      } catch (err) { alert("Error deleting.") }
    }
  }

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 font-mono text-slate-600 italic">
      <div className="animate-pulse">Connecting to Baalebos Cloud Engine...</div>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <header className="mb-10 flex justify-between items-center max-w-7xl mx-auto">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Baalebos Cloud</h1>
          <p className="text-slate-500 text-sm">Global AI Talent Engine • v1.5</p>
        </div>
        <div className="flex items-center gap-4">
          {!isAuthenticated ? (
            <div className="flex gap-2">
              <a href="/login" className="text-sm font-bold text-slate-600 px-4 py-2 hover:text-emerald-600 transition-all">
                Login
              </a>
              <a href="/signup" className="text-sm font-bold text-white bg-emerald-600 px-4 py-2 rounded-lg hover:bg-emerald-700 transition-all shadow-md shadow-emerald-100">
                Sign Up
              </a>
            </div>
          ) : (
            <button 
              onClick={handleLogout}
              className="text-sm font-bold text-rose-600 bg-rose-50 px-4 py-2 rounded-lg hover:bg-rose-100 transition-all"
            >
              Logout
            </button>
          )}
          <div className="hidden md:block bg-slate-200 text-slate-600 px-3 py-1 rounded-full text-xs font-bold uppercase">
            System Live
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto">
        {data.stats && <StatsGrid stats={data.stats} />}

        <div className="mt-12 space-y-16">
          <section className="relative">
            <div className="mb-6 flex justify-between items-end">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">AI Resume Optimizer</h2>
                <p className="text-slate-500 text-sm">Upload for instant global tech matching</p>
              </div>
              {analysisResult && (
                <button onClick={() => setAnalysisResult(null)} className="text-emerald-600 text-sm font-bold hover:underline">+ New Analysis</button>
              )}
            </div>

            {isAnalyzing ? (
              <div className="bg-white p-12 rounded-2xl border border-dashed border-emerald-200 text-center animate-pulse">
                <div className="text-emerald-500 text-4xl mb-4">🚀</div>
                <h3 className="text-lg font-bold text-slate-700">Baalebos AI is calculating...</h3>
              </div>
            ) : !analysisResult ? (
              <ResumeUpload onUploadSuccess={(taskId) => setActiveTaskId(taskId)} />
            ) : (
              <AtsResultView data={analysisResult} />
            )}
          </section>

          <section>
            <h2 className="text-2xl font-bold text-slate-800 mb-6">Application Tracker</h2>
            <ApplicationsTable applications={data.apps} onDelete={handleWithdraw} />
          </section>

          <section className="pb-20">
            <h2 className="text-2xl font-bold text-slate-800 mb-6">Global Tech Discovery</h2>
            <JobFeed jobs={data.availableJobs} onApply={(id) => console.log("Apply to:", id)} />
          </section>
        </div>
      </div>
    </div>
  )
}

// --- MAIN ROUTER ---
function App() {
  const token = localStorage.getItem("token");

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route
          path="/signup"
          element={!token ? <Signup /> : <Navigate to="/" />}
        />
        <Route
          path="/login"
          element={!token ? <Login /> : <Navigate to="/" />}
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  )
}

export default App
