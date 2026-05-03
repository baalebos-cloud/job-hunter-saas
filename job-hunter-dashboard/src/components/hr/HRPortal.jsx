import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const h = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

const WORK_TYPES = ['remote', 'hybrid', 'onsite'];
const CATEGORIES = [
  'Software Engineer', 'Frontend Developer', 'Backend Engineer', 'Full Stack Developer',
  'DevOps Engineer', 'Cloud Engineer', 'Data Engineer', 'Data Scientist',
  'Machine Learning Engineer', 'Mobile Developer', 'QA Engineer', 'Product Manager',
  'UI/UX Designer', 'Cybersecurity Engineer', 'Platform Engineer',
  'Sales', 'Marketing', 'Customer Support', 'Finance', 'Operations',
  'Human Resources', 'Legal', 'Content Writer', 'Graphic Designer',
  'Business Analyst', 'Project Manager', 'Scrum Master',
];

export default function HRPortal() {
  const [dashboard, setDashboard] = useState(null);
  const [myJobs, setMyJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [applications, setApplications] = useState([]);
  const [tab, setTab] = useState('post');
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [msg, setMsg] = useState('');
  const [categoryQuery, setCategoryQuery] = useState('Software Engineer');
  const [showCatSuggestions, setShowCatSuggestions] = useState(false);
  const catRef = useRef(null);
  const [form, setForm] = useState({
    title: '', company: '', location: '', description: '',
    salary_range: '', work_type: 'remote', category: 'Software Engineer', url: ''
  });

  useEffect(() => {
    if (!localStorage.getItem('token')) { window.location.href = '/login'; return; }
    axios.get(`${API}/hr/dashboard`, { headers: h() })
      .then(r => setDashboard(r.data))
      .catch(e => { if (e.response?.status === 403) { alert('HR access required. Contact admin.'); window.location.href = '/'; } })
      .finally(() => setLoading(false));
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const r = await axios.get(`${API}/hr/jobs`, { headers: h() });
      setMyJobs(r.data);
    } catch {}
  };

  const loadApplications = async (jobId) => {
    setSelectedJob(jobId);
    const r = await axios.get(`${API}/hr/jobs/${jobId}/applications`, { headers: h() });
    setApplications(r.data);
    setTab('applications');
  };

  const postJob = async (e) => {
    e.preventDefault();
    setPosting(true);
    try {
      await axios.post(`${API}/hr/jobs`, form, { headers: h() });
      setMsg('✅ Job posted successfully! It\'s now live in the job feed.');
      setForm({ title: '', company: '', location: '', description: '', salary_range: '', work_type: 'remote', category: 'Software Engineer', url: '' });
      loadJobs();
      setTab('my-jobs');
    } catch (e) {
      setMsg(`❌ ${e.response?.data?.detail || 'Failed to post job'}`);
    } finally { setPosting(false); }
  };

  const deleteJob = async (id) => {
    if (!confirm('Delete this job posting?')) return;
    await axios.delete(`${API}/hr/jobs/${id}`, { headers: h() });
    loadJobs();
  };

  const updateStatus = async (appId, status) => {
    await axios.patch(`${API}/hr/applications/${appId}/status?new_status=${status}`, {}, { headers: h() });
    if (selectedJob) loadApplications(selectedJob);
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const inputCls = 'w-full px-4 py-3 rounded-xl border-2 border-slate-700 bg-slate-800 text-white text-sm font-semibold outline-none focus:border-emerald-500 transition-all placeholder:text-slate-500';
  const labelCls = 'block text-xs font-black uppercase tracking-widest text-slate-400 mb-2';

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
    </div>
  );

  const TABS = [
    { id: 'post', label: '+ Post Job' },
    { id: 'my-jobs', label: `💼 My Jobs (${myJobs.length})` },
    { id: 'applications', label: `📋 Applications${selectedJob ? ` (${applications.length})` : ''}` },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Navbar */}
      <div className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/" className="text-slate-400 hover:text-white text-sm font-bold">← Home</a>
          <span className="text-slate-700">|</span>
          <h1 className="text-base font-black">HR Portal</h1>
          <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/20 uppercase tracking-widest">HR</span>
        </div>
        {dashboard && (
          <div className="hidden md:flex items-center gap-6 text-xs font-bold text-slate-400">
            <span>Jobs: <span className="text-white">{dashboard.total_jobs_posted}</span></span>
            <span>Applications: <span className="text-white">{dashboard.total_applications}</span></span>
            <span>Interviews: <span className="text-emerald-400">{dashboard.interviews_scheduled}</span></span>
          </div>
        )}
      </div>

      {msg && (
        <div className={`mx-6 mt-4 p-3 rounded-xl text-sm font-bold flex justify-between ${
          msg.startsWith('✅') ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
          : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
        }`}>
          {msg} <button onClick={() => setMsg('')} className="text-slate-500 hover:text-white ml-4">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="px-6 mt-6 flex gap-1 border-b border-slate-800">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-5 py-2.5 text-sm font-black rounded-t-xl transition-all ${
              tab === t.id ? 'bg-slate-800 text-white border-b-2 border-emerald-500' : 'text-slate-500 hover:text-white'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-6 max-w-4xl">

        {/* Post Job */}
        {tab === 'post' && (
          <form onSubmit={postJob} className="space-y-5">
            <div>
              <h2 className="text-2xl font-black text-white mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>Post a New Job</h2>
              <p className="text-slate-400 text-sm">Your job will appear live in the global feed immediately after posting.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Job Title *</label>
                <input required className={inputCls} placeholder="e.g. Senior DevOps Engineer"
                  value={form.title} onChange={e => set('title', e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Company Name *</label>
                <input required className={inputCls} placeholder="Your company name"
                  value={form.company} onChange={e => set('company', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Location *</label>
                <input required className={inputCls} placeholder="e.g. Lagos, Nigeria / Remote"
                  value={form.location} onChange={e => set('location', e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Salary Range</label>
                <input className={inputCls} placeholder="e.g. $80k - $120k / ₦500k - ₦800k"
                  value={form.salary_range} onChange={e => set('salary_range', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Work Type</label>
                <div className="relative">
                  <select className={`${inputCls} appearance-none pr-8 cursor-pointer`}
                    value={form.work_type} onChange={e => set('work_type', e.target.value)}>
                    {WORK_TYPES.map(w => <option key={w} value={w} style={{ background: '#1e293b' }}>{w.charAt(0).toUpperCase() + w.slice(1)}</option>)}
                  </select>
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none text-xs">▾</span>
                </div>
              </div>
              <div>
                <label className={labelCls}>Category / Job Type</label>
                <div className="relative" ref={catRef}>
                  <input
                    className={inputCls}
                    placeholder="Type or select a category..."
                    value={categoryQuery}
                    onChange={e => { setCategoryQuery(e.target.value); set('category', e.target.value); setShowCatSuggestions(true); }}
                    onFocus={() => setShowCatSuggestions(true)}
                    onBlur={() => setTimeout(() => setShowCatSuggestions(false), 150)}
                    autoComplete="off"
                  />
                  {showCatSuggestions && (
                    <div className="absolute z-50 w-full mt-1 bg-slate-800 border border-slate-700 rounded-xl shadow-xl overflow-hidden max-h-48 overflow-y-auto">
                      {CATEGORIES.filter(c => c.toLowerCase().includes(categoryQuery.toLowerCase())).map(c => (
                        <button key={c} type="button"
                          onMouseDown={() => { setCategoryQuery(c); set('category', c); setShowCatSuggestions(false); }}
                          className="w-full text-left px-4 py-2.5 text-sm font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors border-b border-slate-700/50 last:border-0">
                          {c}
                        </button>
                      ))}
                      {categoryQuery && !CATEGORIES.some(c => c.toLowerCase() === categoryQuery.toLowerCase()) && (
                        <button type="button"
                          onMouseDown={() => { set('category', categoryQuery); setShowCatSuggestions(false); }}
                          className="w-full text-left px-4 py-2.5 text-sm font-bold text-emerald-400 hover:bg-slate-700 transition-colors">
                          ✚ Use "{categoryQuery}" as custom category
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1">Type any category or pick from suggestions.</p>
              </div>
            </div>

            <div>
              <label className={labelCls}>Application URL (optional)</label>
              <input className={inputCls} placeholder="https://yourcompany.com/careers/job-id"
                value={form.url} onChange={e => set('url', e.target.value)} />
              <p className="text-xs text-slate-500 mt-1">If provided, applicants will be redirected here when they apply.</p>
            </div>

            <div>
              <label className={labelCls}>Full Job Description *</label>
              <textarea required rows={8} className={`${inputCls} resize-none`}
                placeholder="Describe the role, responsibilities, requirements, and what makes your company great..."
                value={form.description} onChange={e => set('description', e.target.value)} />
            </div>

            <button type="submit" disabled={posting}
              className="w-full py-4 rounded-2xl font-black text-sm uppercase tracking-widest bg-emerald-600 hover:bg-emerald-500 text-white transition-all disabled:bg-slate-700 disabled:cursor-not-allowed shadow-xl shadow-emerald-600/20">
              {posting ? '⏳ Posting...' : '🚀 Post Job — Go Live Now'}
            </button>
          </form>
        )}

        {/* My Jobs */}
        {tab === 'my-jobs' && (
          <div className="space-y-4">
            <h2 className="text-xl font-black text-white">My Job Postings</h2>
            {myJobs.length === 0 ? (
              <div className="bg-slate-900 border-2 border-dashed border-slate-700 rounded-2xl p-12 text-center">
                <p className="text-slate-400 font-bold">No jobs posted yet.</p>
                <button onClick={() => setTab('post')} className="mt-4 text-emerald-400 font-black text-sm hover:underline">Post your first job →</button>
              </div>
            ) : myJobs.map(job => (
              <div key={job.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h3 className="font-black text-white text-base">{job.title}</h3>
                  <p className="text-emerald-400 font-bold text-sm mt-0.5">{job.company}</p>
                  <div className="flex gap-3 mt-2 text-xs text-slate-400 font-medium">
                    <span>📍 {job.location}</span>
                    {job.salary_range && <span>💰 {job.salary_range}</span>}
                    <span className="capitalize">🏢 {job.work_type}</span>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => loadApplications(job.id)}
                    className="text-xs font-black px-3 py-2 rounded-xl bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-all">
                    View Applicants
                  </button>
                  <button onClick={() => deleteJob(job.id)}
                    className="text-xs font-black px-3 py-2 rounded-xl bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-all">
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Applications */}
        {tab === 'applications' && (
          <div className="space-y-4">
            <h2 className="text-xl font-black text-white">
              {selectedJob ? `Applicants for Job #${selectedJob}` : 'Select a job to view applicants'}
            </h2>
            {!selectedJob ? (
              <p className="text-slate-400">Go to <button onClick={() => setTab('my-jobs')} className="text-emerald-400 font-bold hover:underline">My Jobs</button> and click "View Applicants".</p>
            ) : applications.length === 0 ? (
              <div className="bg-slate-900 border-2 border-dashed border-slate-700 rounded-2xl p-12 text-center">
                <p className="text-slate-400 font-bold">No applications yet for this job.</p>
              </div>
            ) : applications.map(app => (
              <div key={app.application_id} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-black text-white">{app.applicant_name}</h3>
                    <p className="text-slate-400 text-sm">{app.applicant_email}</p>
                    <div className="flex gap-3 mt-2 text-xs text-slate-500">
                      {app.applicant_country && <span>🌍 {app.applicant_country}</span>}
                      {app.career_track && <span>💼 {app.career_track}</span>}
                      <span>📅 {new Date(app.applied_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className={`text-xs font-black px-2 py-1 rounded-full ${
                      (app.ats_score||0) >= 80 ? 'bg-emerald-500/20 text-emerald-400'
                      : (app.ats_score||0) >= 60 ? 'bg-amber-500/20 text-amber-400'
                      : 'bg-slate-700 text-slate-400'
                    }`}>ATS: {app.ats_score || 0}%</span>
                    <span className={`text-xs font-black px-2 py-1 rounded-full capitalize ${
                      app.status === 'interview' ? 'bg-purple-500/20 text-purple-400'
                      : app.status === 'offer' ? 'bg-emerald-500/20 text-emerald-400'
                      : app.status === 'rejected' ? 'bg-rose-500/20 text-rose-400'
                      : 'bg-slate-700 text-slate-400'
                    }`}>{app.status}</span>
                  </div>
                </div>
                {/* Status actions */}
                <div className="flex gap-2 mt-4 flex-wrap">
                  {['reviewed', 'interview', 'offer', 'rejected'].map(s => (
                    <button key={s} onClick={() => updateStatus(app.application_id, s)}
                      disabled={app.status === s}
                      className={`text-xs font-black px-3 py-1.5 rounded-xl transition-all capitalize ${
                        app.status === s ? 'bg-slate-700 text-slate-500 cursor-default'
                        : s === 'interview' ? 'bg-purple-500/10 text-purple-400 hover:bg-purple-500/20'
                        : s === 'offer' ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                        : s === 'rejected' ? 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}>
                      {s === 'interview' ? '📅 Schedule Interview' : s === 'offer' ? '🎉 Send Offer' : s === 'rejected' ? '❌ Reject' : '👁 Mark Reviewed'}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
