import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'

// Components
import StatsGrid from './components/StatsGrid'
import ApplicationsTable from './components/dashboard/ApplicationsTable'
import JobFeed from './components/JobFeed'
import ResumeUpload from './components/dashboard/ResumeUpload'
import AtsResultView from './components/dashboard/AtsResultView'
import Signup from './components/auth/Signup'
import Login from './components/auth/Login'

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://baalebo.xyz";

const Dashboard = () => {
  const [data, setData] = useState({ stats: null, apps: [], availableJobs: [] })
  const [loading, setLoading] = useState(true)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [activeTaskId, setActiveTaskId] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const token = localStorage.getItem("token");
  const isAuthenticated = !!token;

  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
      
      // We fetch jobs for everyone, but stats/apps only for logged-in users
      const requests = [
        axios.get(`${API_BASE_URL}/jobs/`)
      ];

      if (token) {
        requests.push(axios.get(`${API_BASE_URL}/dashboard/stats`, config));
        requests.push(axios.get(`${API_BASE_URL}/dashboard/applied`, config));
      }

      const results = await Promise.allSettled(requests);
      
      // Logic to map results correctly based on authentication
      const jobsRes = results[0];
      const statsRes = token ? results[1] : null;
      const appsRes = token ? results[2] : null;

      setData({
        availableJobs: jobsRes.status === 'fulfilled' && Array.isArray(jobsRes.value.data) ? jobsRes.value.data : [],
        stats: statsRes?.status === 'fulfilled' ? statsRes.value.data : null,
        apps: appsRes?.status === 'fulfilled' && Array.isArray(appsRes.value.data) ? appsRes.value.data : []
      });
    } catch (err) {
      console.error("Data Fetch Error:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Handle Resume Polling Logic
  useEffect(() => {
    let interval;
    if (activeTaskId) {
      setIsAnalyzing(true);
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE_URL}/resume/status/${activeTaskId}`);
          if (res.data.status === "completed") {
            setAnalysisResult(res.data.result);
            setActiveTaskId(null);
            setIsAnalyzing(false);
            fetchData(); // Refresh tracker if user is logged in
          } else if (res.data.status === "failed") {
            alert("Analysis failed. Please check your file format.");
            setActiveTaskId(null);
            setIsAnalyzing(false);
          }
        } catch (err) { console.error("Polling error:", err); }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [activeTaskId, fetchData]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 font-mono text-slate-600 italic">
      <div className="animate-pulse">Connecting to Baalebos Cloud Engine...</div>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <header className="mb-10 flex justify-between items-center max-w-7xl mx-auto">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tighter">BAALEBOS CLOUD</h1>
          <p className="text-slate-400 text-[10px] font-black uppercase tracking-[0.2em]">AI Talent Infrastructure</p>
        </div>
        <div className="flex items-center gap-4">
          {!isAuthenticated ? (
            <div className="flex gap-2">
              <a href="/login" className="text-sm font-bold text-slate-600 px-4 py-2 hover:text-emerald-600 transition-all">Login</a>
              <a href="/signup" className="text-sm font-bold text-white bg-emerald-600 px-5 py-2.5 rounded-xl hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-100">Sign Up</a>
            </div>
          ) : (
            <button onClick={handleLogout} className="text-sm font-bold text-rose-600 bg-rose-50 px-4 py-2 rounded-lg hover:bg-rose-100 transition-all">Logout</button>
          )}
        </div>
      </header>

      <div className="max-w-7xl mx-auto">
        {/* PUBLIC SECTION: Resume Optimizer (Shown to everyone) */}
        <section className="mb-16">
          <div className="mb-8 flex justify-between items-end">
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900">AI Resume Optimizer</h2>
              <p className="text-slate-500 font-medium">Upload, select your track, and analyze for global matching.</p>
            </div>
            {analysisResult && (
              <button onClick={() => setAnalysisResult(null)} className="text-emerald-600 text-sm font-black uppercase tracking-widest hover:underline">
                + New Analysis
              </button>
            )}
          </div>

          {isAnalyzing ? (
            <div className="bg-white p-16 rounded-[2rem] border-2 border-dashed border-emerald-200 text-center animate-pulse shadow-xl shadow-emerald-900/5">
              <div className="text-emerald-500 text-5xl mb-4">🚀</div>
              <h3 className="text-xl font-black text-slate-800 uppercase tracking-tight">Processing through AI Core...</h3>
              <p className="text-slate-400 mt-2 font-medium">Calculating ATS scores and skill gaps...</p>
            </div>
          ) : !analysisResult ? (
            <div className="bg-white rounded-[2rem] shadow-xl shadow-slate-200/50 overflow-hidden border border-slate-100">
               <ResumeUpload onUploadSuccess={(taskId) => setActiveTaskId(taskId)} />
            </div>
          ) : (
            <AtsResultView data={analysisResult} />
          )}
        </section>

        {/* PRIVATE SECTION: Stats and Tracker (Requires Login) */}
        {isAuthenticated ? (
          <div className="space-y-16 border-t border-slate-200 pt-16">
            {data.stats && <StatsGrid stats={data.stats} />}
            
            <section>
              <h2 className="text-2xl font-black text-slate-800 mb-6 flex items-center gap-3">
                 <span className="w-2 h-8 bg-emerald-500 rounded-full"></span>
                 Your Application Tracker
              </h2>
              <ApplicationsTable applications={data.apps || []} />
            </section>
          </div>
        ) : (
          <div className="bg-slate-900 rounded-[2rem] p-10 text-center text-white mb-16 shadow-2xl">
             <h3 className="text-xl font-bold mb-2">Want to track your progress?</h3>
             <p className="text-slate-400 mb-6 text-sm">Create an account to save your AI scores and track job applications.</p>
             <a href="/signup" className="inline-block bg-emerald-500 text-white font-black px-8 py-3 rounded-xl hover:bg-emerald-400 transition-all uppercase tracking-widest text-xs">Join the Infrastructure</a>
          </div>
        )}

        {/* SEMI-PUBLIC SECTION: Job Feed (Shown to everyone) */}
        <section className="pb-24">
          <h2 className="text-2xl font-black text-slate-800 mb-6 flex items-center gap-3">
             <span className="w-2 h-8 bg-blue-500 rounded-full"></span>
             Global Tech Discovery
          </h2>
          <JobFeed jobs={data.availableJobs || []} />
        </section>
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
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  )
}

export default App
