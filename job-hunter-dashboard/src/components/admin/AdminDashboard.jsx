import { useState, useEffect } from 'react';
import axios from 'axios';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const h = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [apps, setApps] = useState([]);
  const [tab, setTab] = useState('stats');
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (!localStorage.getItem('token')) { window.location.href = '/login'; return; }
    axios.get(`${API}/admin/stats`, { headers: h() })
      .then(r => setStats(r.data))
      .catch(e => { if (e.response?.status === 403) { alert('Admin access required'); window.location.href = '/'; } })
      .finally(() => setLoading(false));
  }, []);

  const load = async (t) => {
    setTab(t);
    if (t === 'users')   { const r = await axios.get(`${API}/admin/users`, { headers: h() }); setUsers(r.data); }
    if (t === 'jobs')    { const r = await axios.get(`${API}/admin/jobs`, { headers: h() }); setJobs(r.data); }
    if (t === 'apps')    { const r = await axios.get(`${API}/admin/applications`, { headers: h() }); setApps(r.data); }
  };

  const makeHR = async (id) => {
    await axios.patch(`${API}/admin/users/${id}/make-hr`, {}, { headers: h() });
    setMsg('User promoted to HR'); load('users');
  };

  const delUser = async (id) => {
    if (!confirm('Delete user?')) return;
    await axios.delete(`${API}/admin/users/${id}`, { headers: h() }); load('users');
  };

  const delJob = async (id) => {
    if (!confirm('Delete job?')) return;
    await axios.delete(`${API}/admin/jobs/${id}`, { headers: h() }); load('jobs');
  };

  const scrape = async () => {
    setScraping(true);
    try {
      const r = await axios.post(`${API}/admin/scrape`, {}, { headers: h() });
      setMsg(`✅ Scrape done: ${r.data.total_saved} new jobs`);
      const s = await axios.get(`${API}/admin/stats`, { headers: h() }); setStats(s.data);
    } catch { setMsg('❌ Scrape failed'); } finally { setScraping(false); }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  );

  const TABS = [
    { id: 'stats', label: '📊 Stats' },
    { id: 'users', label: '👥 Users' },
    { id: 'jobs',  label: '💼 Jobs' },
    { id: 'apps',  label: '📋 Applications' },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Navbar */}
      <div className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/" className="text-slate-400 hover:text-white text-sm font-bold">← Home</a>
          <span className="text-slate-700">|</span>
          <h1 className="text-base font-black">Admin Dashboard</h1>
          <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/20 uppercase tracking-widest">Admin</span>
        </div>
        <button onClick={scrape} disabled={scraping}
          className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-black transition-all disabled:bg-slate-700 disabled:cursor-not-allowed">
          {scraping ? '⏳ Scraping...' : '🔄 Run Scraper'}
        </button>
      </div>

      {msg && (
        <div className="mx-6 mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm font-bold flex justify-between">
          {msg} <button onClick={() => setMsg('')} className="text-slate-500 hover:text-white ml-4">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="px-6 mt-6 flex gap-1 border-b border-slate-800">
        {TABS.map(t => (
          <button key={t.id} onClick={() => load(t.id)}
            className={`px-5 py-2.5 text-sm font-black rounded-t-xl transition-all ${
              tab === t.id ? 'bg-slate-800 text-white border-b-2 border-emerald-500' : 'text-slate-500 hover:text-white'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-6">

        {/* Stats */}
        {tab === 'stats' && stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ['Total Users', stats.total_users, 'text-blue-400'],
              ['Total Jobs', stats.total_jobs, 'text-emerald-400'],
              ['Applications', stats.total_applications, 'text-purple-400'],
              ['Resumes', stats.total_resumes, 'text-amber-400'],
              ['HR Users', stats.hr_users, 'text-pink-400'],
              ['HR Posted Jobs', stats.hr_posted_jobs, 'text-cyan-400'],
              ['New Users Today', stats.new_users_today, 'text-green-400'],
            ].map(([label, value, color]) => (
              <div key={label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <div className={`text-3xl font-black ${color}`}>{value ?? 0}</div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-1">{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Users */}
        {tab === 'users' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50">
                <tr>{['Name','Email','Country','Track','Role','Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {users.map(u => (
                  <tr key={u.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-semibold text-white">{u.full_name || '—'}</td>
                    <td className="px-4 py-3 text-slate-400">{u.email}</td>
                    <td className="px-4 py-3 text-slate-400">{u.country || '—'}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{u.career_track || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-black px-2 py-0.5 rounded-full ${
                        u.is_admin ? 'bg-purple-500/20 text-purple-400'
                        : u.is_hr ? 'bg-blue-500/20 text-blue-400'
                        : 'bg-slate-700 text-slate-400'
                      }`}>{u.is_admin ? 'Admin' : u.is_hr ? 'HR' : 'User'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {!u.is_hr && !u.is_admin && (
                          <button onClick={() => makeHR(u.id)}
                            className="text-xs font-bold px-2 py-1 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20">
                            Make HR
                          </button>
                        )}
                        <button onClick={() => delUser(u.id)}
                          className="text-xs font-bold px-2 py-1 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Jobs */}
        {tab === 'jobs' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50">
                <tr>{['Title','Company','Location','Source','Work Type','Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {jobs.map(j => (
                  <tr key={j.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-semibold text-white">{j.title}</td>
                    <td className="px-4 py-3 text-slate-400">{j.company}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{j.location || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${j.posted_by_hr ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-700 text-slate-400'}`}>
                        {j.source || 'Scraped'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 capitalize text-xs">{j.work_type || '—'}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => delJob(j.id)}
                        className="text-xs font-bold px-2 py-1 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Applications */}
        {tab === 'apps' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50">
                <tr>{['Applicant','Job','Company','ATS','Status','Date'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-slate-400">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {apps.map(a => (
                  <tr key={a.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 text-white font-semibold text-xs">{a.user_email}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{a.job_title || '—'}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{a.company || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-black px-2 py-0.5 rounded-full ${
                        (a.ats_score||0) >= 80 ? 'bg-emerald-500/20 text-emerald-400'
                        : (a.ats_score||0) >= 60 ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-slate-700 text-slate-400'
                      }`}>{a.ats_score || 0}%</span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 capitalize text-xs">{a.status}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{new Date(a.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
