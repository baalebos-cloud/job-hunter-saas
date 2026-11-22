import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Briefcase, FileUp, Loader2, X } from 'lucide-react';
import { errorText } from '../../lib/session';

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

export default function ResumeUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [jobTitle, setJobTitle] = useState('');
  const [jobDesc, setJobDesc] = useState('');
  const [region, setRegion] = useState('');
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState('');
  const [linkedJob, setLinkedJob] = useState(null);
  const inputRef = useRef(null);
  const dropRef = useRef(null);

  useEffect(() => {
    // "Tailor again" from My resumes: reuse that job's title and description once.
    try {
      const again = JSON.parse(sessionStorage.getItem('tailorAgain') || 'null');
      sessionStorage.removeItem('tailorAgain');
      if (again && !new URLSearchParams(window.location.search).get('job')) {
        setJobTitle(again.title || ''); setQuery(again.title || ''); setJobDesc(again.description || '');
      }
    } catch { /* storage unavailable: start empty */ }
    const jobId = new URLSearchParams(window.location.search).get('job');
    if (!jobId) return;
    axios.get(`${API_BASE_URL}/jobs/detail/${jobId}`).then(({data})=>{
      setJobTitle(data.title); setQuery(data.title); setJobDesc(data.description || ''); setLinkedJob(data);
    }).catch(()=>setError('Could not load that job. Paste its job description below instead.'));
  }, []);

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
    if (!token) { window.location.href = '/login'; return; }
    if (!file || !jobTitle || !jobDesc) { setError('Add your resume, the job title and the job description.'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('Your resume must be 10 MB or smaller.'); return; }

    setUploading(true); setError('');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_description', jobDesc);
    formData.append('job_title', jobTitle.trim());
    if (region) formData.append('region', region);
    if (linkedJob?.id) formData.append('job_id', String(linkedJob.id));   // shown in My resumes

    try {
      const res = await axios.post(`${API_BASE_URL}/resume/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data', Authorization: `Bearer ${token}` },
        timeout: 300000  // 5 minutes: tailoring calls the AI provider several times
      });
      if (res.data.result) {
        // Direct result returned (Railway mode — no Celery)
        if (onUploadSuccess) onUploadSuccess(res.data.task_id, res.data.result);
      } else if (res.data.task_id) {
        // Async Celery mode (local dev)
        if (onUploadSuccess) onUploadSuccess(res.data.task_id, null);
      } else {
        setError('The server accepted the file but returned no result. Please retry.');
      }
    } catch (err) {
      setError(errorText(err, 'Upload failed. Please try again.'));
    } finally {
      setUploading(false);
    }
  };

  const inputCls = 'w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40';
  const ready = file && jobTitle.trim() && jobDesc.trim();

  return (
    <form onSubmit={handleUpload} className="space-y-4" noValidate>
      <section className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6" aria-labelledby="step-resume">
        <h3 id="step-resume" className="font-semibold text-slate-900"><span className="text-emerald-700">1 ·</span> Your resume</h3>
        <input type="file" id="resume-file" name="file" className="hidden" accept=".pdf,.docx"
          onChange={e => { setFile(e.target.files?.[0] || null); setError(''); }} />
        <label htmlFor="resume-file"
          className={`mt-3 flex items-center gap-4 p-4 rounded-xl border-2 border-dashed cursor-pointer transition-colors ${file ? 'border-emerald-400 bg-emerald-50/50' : 'border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30'}`}>
          <span className={`w-11 h-11 rounded-xl grid place-items-center shrink-0 ${file ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}><FileUp size={20} /></span>
          <span className="min-w-0">
            <span className="block font-medium text-sm text-slate-900 truncate">{file ? file.name : 'Choose your current resume'}</span>
            <span className="block text-xs text-slate-500">{file ? `${(file.size / 1024).toFixed(0)} KB · click to change` : 'PDF or DOCX, up to 10 MB'}</span>
          </span>
        </label>
        <div className="mt-4 grid sm:grid-cols-2 gap-4 items-start">
          <label className="block text-sm font-medium text-slate-700" htmlFor="resume-region">Resume convention
            <select id="resume-region" value={region} onChange={e => setRegion(e.target.value)} className={`${inputCls} mt-1.5`}>
              <option value="">Auto (from my profile country)</option>
              <option value="US">United States (Letter)</option>
              <option value="CA">Canada (Letter)</option>
              <option value="UK">United Kingdom (A4)</option>
              <option value="EU">European Union (A4)</option>
              <option value="NG">Nigeria (A4)</option>
              <option value="OTHER">Other / international (A4)</option>
            </select>
          </label>
          <p className="text-xs text-slate-500 sm:mt-7">One page, no watermark. Employers, titles, dates, degrees and certifications are always kept.</p>
        </div>
      </section>

      <section className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6" aria-labelledby="step-job">
        <h3 id="step-job" className="font-semibold text-slate-900"><span className="text-emerald-700">2 ·</span> Target job</h3>
        {linkedJob ? (
          <div className="mt-3 flex items-start gap-3 rounded-xl bg-slate-50 border border-slate-200 p-4">
            <Briefcase size={18} className="mt-0.5 text-slate-500 shrink-0" />
            <div className="flex-1 min-w-0"><p className="font-medium text-slate-900">{linkedJob.title}</p>
              <p className="text-sm text-slate-600">{[linkedJob.company, linkedJob.location].filter(Boolean).join(' · ')}</p>
              <p className="text-xs text-slate-500 mt-1">The job description was filled in from the job board. You can edit it below.</p></div>
            <button type="button" aria-label="Use a different job" onClick={() => { setLinkedJob(null); setJobTitle(''); setQuery(''); setJobDesc(''); window.history.replaceState(null, '', '/optimizer'); }}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200"><X size={16} /></button>
          </div>
        ) : (
          <p className="mt-1 text-sm text-slate-500">Paste the job you are applying for, or pick one on the <a href="/jobs" className="font-semibold text-emerald-700 hover:underline">job board</a> and choose “Tailor my resume to this job”.</p>
        )}
        <div className="mt-4 relative" ref={dropRef}>
          <label htmlFor="resume-job-title" className="block text-sm font-medium text-slate-700">Job title</label>
          <input ref={inputRef} id="resume-job-title" name="job_title" type="text" autoComplete="off"
            placeholder="e.g. Senior DevOps Engineer" className={`${inputCls} mt-1.5`} value={query}
            onChange={e => { setQuery(e.target.value); setJobTitle(e.target.value); setShowSuggestions(true); }}
            onFocus={() => setShowSuggestions(true)} />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute z-30 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden" role="listbox">
              {suggestions.map(title => (
                <li key={title}><button type="button" onMouseDown={() => selectTitle(title)} className="w-full text-left px-3.5 py-2.5 text-sm text-slate-700 hover:bg-emerald-50">{title}</button></li>))}
            </ul>)}
        </div>
        <label htmlFor="resume-job-description" className="mt-4 block text-sm font-medium text-slate-700">Job description</label>
        <textarea id="resume-job-description" name="job_description" rows={8} className={`${inputCls} mt-1.5 leading-relaxed`}
          placeholder="Paste the full job description, including responsibilities and requirements."
          value={jobDesc} onChange={e => setJobDesc(e.target.value)} />
        <p className="mt-1 text-xs text-slate-500">The full description gives the most accurate match. {jobDesc.trim() ? `${jobDesc.trim().split(/\s+/).length} words.` : ''}</p>
      </section>

      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <button type="submit" disabled={uploading || !ready}
        className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed">
        {uploading && <Loader2 size={16} className="animate-spin" />}
        {uploading ? 'Matching your resume…' : 'Match and tailor my resume'}
      </button>
      {!ready && <p className="text-xs text-slate-500">{!file ? 'Step 1: choose your resume.' : !jobTitle.trim() ? 'Step 2: add the job title.' : 'Step 2: paste the job description.'}</p>}
    </form>
  );
}
