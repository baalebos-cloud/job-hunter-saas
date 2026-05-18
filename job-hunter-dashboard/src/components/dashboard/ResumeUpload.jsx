import { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Comprehensive job title list — users can also type anything custom
const ALL_JOB_TITLES = [
  'Software Engineer', 'Senior Software Engineer', 'Staff Software Engineer',
  'Frontend Developer', 'Senior Frontend Developer', 'React Developer', 'Vue Developer', 'Angular Developer',
  'Backend Developer', 'Senior Backend Developer', 'Python Developer', 'Node.js Developer',
  'Java Developer', 'Go Developer', 'Ruby on Rails Developer', 'PHP Developer', 'Rust Developer',
  'Full Stack Developer', 'Senior Full Stack Developer',
  'DevOps Engineer', 'Senior DevOps Engineer', 'Lead DevOps Engineer',
  'Cloud Engineer', 'AWS Engineer', 'GCP Engineer', 'Azure Engineer', 'Cloud Architect',
  'Platform Engineer', 'Infrastructure Engineer', 'Site Reliability Engineer (SRE)',
  'Data Engineer', 'Senior Data Engineer', 'Data Architect',
  'Data Scientist', 'Senior Data Scientist', 'ML Engineer', 'Machine Learning Engineer',
  'AI Engineer', 'AI/ML Engineer', 'LLM Engineer', 'NLP Engineer',
  'Data Analyst', 'Business Intelligence Analyst', 'Analytics Engineer',
  'Cybersecurity Engineer', 'Security Analyst', 'Penetration Tester', 'SOC Analyst',
  'Mobile Developer', 'iOS Developer', 'Android Developer', 'Flutter Developer', 'React Native Developer',
  'QA Engineer', 'SDET', 'Test Automation Engineer',
  'Product Manager', 'Senior Product Manager', 'Technical Product Manager',
  'UI/UX Designer', 'Product Designer', 'UX Researcher',
  'Blockchain Developer', 'Web3 Developer', 'Solidity Developer',
  'Embedded Systems Engineer', 'Firmware Engineer', 'C++ Developer',
  'Database Administrator', 'PostgreSQL DBA', 'MySQL DBA',
  'Technical Lead', 'Engineering Manager', 'VP of Engineering', 'CTO',
  'Solutions Architect', 'Enterprise Architect', 'Technical Architect',
  'Scrum Master', 'Agile Coach', 'Project Manager',
  'Network Engineer', 'Systems Administrator', 'Linux Administrator',
  'Salesforce Developer', 'SAP Consultant', 'ERP Developer',
];

const WORK_TYPES = [
  { value: 'remote',  label: '🌍 Remote',   desc: 'Work from anywhere' },
  { value: 'hybrid',  label: '🏢 Hybrid',   desc: 'Mix of office & remote' },
  { value: 'onsite',  label: '📍 On-site',  desc: 'Full-time in office' },
];

export default function ResumeUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [jobTitle, setJobTitle] = useState('');
  const [jobDesc, setJobDesc] = useState('');
  const [workType, setWorkType] = useState('remote');
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef(null);
  const dropRef = useRef(null);

  // Filter suggestions based on query
  const suggestions = query.length >= 1
    ? ALL_JOB_TITLES.filter(t => t.toLowerCase().includes(query.toLowerCase())).slice(0, 8)
    : [];

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selectTitle = (title) => {
    setJobTitle(title);
    setQuery(title);
    setShowSuggestions(false);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const token = localStorage.getItem('token');
    if (!token) { alert('Please login to use the AI Optimizer.'); window.location.href = '/login'; return; }
    if (!file || !jobTitle || !jobDesc) { alert('Please fill in all fields and upload your resume.'); return; }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_description', jobDesc);
    formData.append('job_title', jobTitle.trim());
    formData.append('work_type', workType);

    try {
      const res = await axios.post(`${API_BASE_URL}/resume/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data', Authorization: `Bearer ${token}` },
        timeout: 120000  // 2 minutes — AI analysis takes time
      });
      if (res.data.result) {
        // Direct result returned (Railway mode — no Celery)
        if (onUploadSuccess) onUploadSuccess(res.data.task_id, res.data.result);
      } else if (res.data.task_id) {
        // Async Celery mode (local dev)
        if (onUploadSuccess) onUploadSuccess(res.data.task_id, null);
      } else {
        alert("Server received the file but didn't return a result.");
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Upload failed. Please try again.';
      alert(typeof msg === 'string' ? msg : 'Check all fields and try again.');
    } finally {
      setUploading(false);
    }
  };

  const inputCls = 'w-full px-4 py-3.5 rounded-2xl border-2 border-slate-200 bg-white outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all text-slate-900 font-semibold text-sm placeholder:text-slate-400';

  return (
    <div className="bg-white p-8 md:p-12 rounded-[2rem] shadow-2xl shadow-slate-200/50 border border-slate-100 max-w-3xl mx-auto my-8"
      style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Header */}
      <div className="text-center mb-10">
        <h2 className="text-3xl font-black text-slate-900 tracking-tight"
          style={{ fontFamily: "'Playfair Display', serif" }}>AI Resume Optimizer</h2>
        <p className="text-slate-500 font-medium mt-2 text-sm">
          Our AI scores your resume against the job description and generates an interview-ready PDF.
        </p>
      </div>

      <form onSubmit={handleUpload} className="space-y-6">

        {/* Job Title — searchable autocomplete */}
        <div>
          <label className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">
            Target Job Title
          </label>
          <div className="relative" ref={dropRef}>
            <div className="relative">
              <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={inputRef}
                type="text"
                placeholder="Search or type any job title... e.g. Senior DevOps Engineer"
                className={`${inputCls} pl-11 pr-10`}
                value={query}
                onChange={e => { setQuery(e.target.value); setJobTitle(e.target.value); setShowSuggestions(true); }}
                onFocus={() => setShowSuggestions(true)}
                autoComplete="off"
              />
              {query && (
                <button type="button" onClick={() => { setQuery(''); setJobTitle(''); inputRef.current?.focus(); }}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 font-black text-lg">
                  ×
                </button>
              )}
            </div>

            {/* Suggestions dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-50 w-full mt-1 bg-white border-2 border-slate-200 rounded-2xl shadow-xl overflow-hidden">
                {suggestions.map(title => (
                  <button
                    key={title}
                    type="button"
                    onMouseDown={() => selectTitle(title)}
                    className="w-full text-left px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 transition-colors border-b border-slate-50 last:border-0"
                  >
                    {title}
                  </button>
                ))}
                {query && !ALL_JOB_TITLES.some(t => t.toLowerCase() === query.toLowerCase()) && (
                  <button
                    type="button"
                    onMouseDown={() => selectTitle(query)}
                    className="w-full text-left px-4 py-3 text-sm font-bold text-emerald-600 hover:bg-emerald-50 transition-colors bg-emerald-50/50">
                    ✚ Use "{query}" as custom title
                  </button>
                )}
              </div>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1.5 ml-1 font-medium">
            Type to search from 60+ roles or enter any custom title.
          </p>
        </div>

        {/* Work Type */}
        <div>
          <label className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-3">
            Preferred Work Type
          </label>
          <div className="grid grid-cols-3 gap-3">
            {WORK_TYPES.map(wt => (
              <button
                key={wt.value}
                type="button"
                onClick={() => setWorkType(wt.value)}
                className={`p-4 rounded-2xl border-2 text-left transition-all ${
                  workType === wt.value
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <p className={`text-sm font-black ${
                  workType === wt.value ? 'text-emerald-700' : 'text-slate-700'
                }`}>
                  {wt.label}
                </p>
                <p className={`text-xs font-medium mt-0.5 ${
                  workType === wt.value ? 'text-emerald-600' : 'text-slate-400'
                }`}>
                  {wt.desc}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Job Description */}
        <div>
          <label className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">
            Job Description
          </label>
          <textarea
            rows={5}
            required
            placeholder="Paste the full job description here — the AI will extract every keyword and score your resume against it for maximum ATS match..."
            className={`${inputCls} resize-none leading-relaxed`}
            value={jobDesc}
            onChange={e => setJobDesc(e.target.value)}
          />
          <p className="text-xs text-slate-400 mt-1.5 ml-1 font-medium">
            The more complete the JD, the higher your ATS score will be.
          </p>
        </div>

        {/* File Upload */}
        <div>
          <label className="block text-xs font-black uppercase tracking-widest text-slate-500 mb-2">
            Your Resume
          </label>
          <input type="file" id="resume-file" className="hidden"
            onChange={e => setFile(e.target.files?.[0] || null)} accept=".pdf,.docx,.doc" />
          <label htmlFor="resume-file"
            className={`flex items-center gap-4 p-5 rounded-2xl border-2 border-dashed cursor-pointer transition-all ${
              file ? 'border-emerald-400 bg-emerald-50/40' : 'border-slate-200 bg-slate-50/50 hover:border-emerald-300 hover:bg-emerald-50/20'
            }`}>
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl shrink-0 ${
              file ? 'bg-emerald-100' : 'bg-slate-100'
            }`}>
              {file ? '✅' : '📄'}
            </div>
            <div>
              <p className={`font-black text-sm ${
                file ? 'text-emerald-700' : 'text-slate-700'
              }`}>
                {file ? file.name : 'Click to upload your resume'}
              </p>
              <p className="text-xs font-medium text-slate-400 mt-0.5">
                {file ? `${(file.size / 1024).toFixed(0)} KB · PDF, DOCX or DOC` : 'PDF, DOCX, or DOC · Max 10MB'}
              </p>
            </div>
          </label>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={uploading || !file || !jobTitle || !jobDesc}
          className={`w-full py-5 rounded-2xl font-black text-sm uppercase tracking-widest text-white shadow-xl transition-all active:scale-95 ${
            uploading || !file || !jobTitle || !jobDesc
              ? 'bg-slate-300 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/20'
          }`}
        >
          {uploading ? '🚀 AI Analyzing Your Resume...' : 'Run AI Analysis & Get Interview-Ready PDF →'}
        </button>

        {(!file || !jobTitle || !jobDesc) && (
          <p className="text-center text-xs text-slate-400 font-medium">
            {!jobTitle ? '① Search and select a job title above'
              : !jobDesc ? '② Paste the job description'
              : '③ Upload your resume to start'}
          </p>
        )}
      </form>
    </div>
  );
}