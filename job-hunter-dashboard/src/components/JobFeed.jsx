// =============================================================================
// job-hunter-dashboard/src/components/JobFeed.jsx
//  1. Tech grid background on job cards
//  2. Pagination — 12 cards per page with prev/next
//  3. Improved UI — source badge, category chip, hover effects
// =============================================================================
import React, { useState } from 'react';
import axios from 'axios';
import { MapPin, DollarSign, Send, X, ExternalLink, FileText, CheckCircle, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const JOBS_PER_PAGE = 12;

const workType = (loc, wt) => {
  const check = (wt || loc || '').toLowerCase();
  if (check.includes('hybrid'))   return { label: 'Hybrid',  cls: 'bg-violet-100 text-violet-700 border-violet-200' };
  if (check.includes('on-site') || check.includes('onsite') || check.includes('office'))
    return { label: 'On-site', cls: 'bg-orange-100 text-orange-700 border-orange-200' };
  return { label: 'Remote', cls: 'bg-sky-100 text-sky-700 border-sky-200' };
};

const sourceColor = (source) => {
  const s = (source || '').toLowerCase();
  if (s.includes('amazon'))    return 'bg-amber-100 text-amber-700';
  if (s.includes('greenhouse')) return 'bg-green-100 text-green-700';
  if (s.includes('lever'))     return 'bg-purple-100 text-purple-700';
  if (s.includes('remotive'))  return 'bg-blue-100 text-blue-700';
  if (s.includes('micro1'))    return 'bg-pink-100 text-pink-700';
  if (s.includes('remoteok'))  return 'bg-teal-100 text-teal-700';
  if (s.includes('jobstash'))  return 'bg-indigo-100 text-indigo-700';
  if (s.includes('skillsire')) return 'bg-emerald-100 text-emerald-700';
  return 'bg-slate-100 text-slate-600';
};

// ── Company Logo ──────────────────────────────────────────────────────────────
function Logo({ company, size = 12 }) {
  const slug = (company || 'c').toLowerCase().replace(/[^a-z0-9]/g, '');
  return (
    <img
      src={`https://logo.clearbit.com/${slug}.com`}
      onError={e => {
        e.target.onerror = null;
        e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(company || 'C')}&background=0f172a&color=10b981&bold=true&size=80`;
      }}
      alt={company}
      className={`w-${size} h-${size} rounded-2xl object-contain bg-slate-50 p-1 border border-slate-100 shrink-0`}
    />
  );
}

// ── Tech grid pattern SVG (inline background) ─────────────────────────────────
const TechGridBg = () => (
  <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
    style={{
      backgroundImage: 'linear-gradient(#10b981 1px, transparent 1px), linear-gradient(90deg, #10b981 1px, transparent 1px)',
      backgroundSize: '24px 24px',
    }}
  />
);

// ── Resume Review Step ────────────────────────────────────────────────────────
function ResumeReviewStep({ job, taskId, onConfirm, onBack, applying }) {
  const token = localStorage.getItem('token');
  const [previewing, setPreviewing] = useState(false);

  const previewResume = async () => {
    if (!token) { window.location.href = '/login'; return; }
    if (!taskId) { alert('No optimized resume found. Run the AI Resume Optimizer first, then apply.'); return; }
    setPreviewing(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/resume/download/${taskId}`, {
        headers: { Authorization: `Bearer ${token}` }, responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      window.open(url, '_blank');
    } catch { alert('Resume preview unavailable. You can still apply.'); }
    finally { setPreviewing(false); }
  };

  return (
    <div className="p-7 space-y-5">
      {/* Step indicator */}
      <div className="flex items-center gap-3 mb-2">
        {[['✓','Job Reviewed','bg-emerald-500 text-white','text-emerald-600'],
          ['2','Review Resume','bg-slate-900 text-white','text-slate-900 font-black'],
          ['3','Confirm Apply','bg-slate-200 text-slate-400','text-slate-400'],
        ].map(([num, label, circleCls, textCls], i) => (
          <React.Fragment key={label}>
            {i > 0 && <div className="flex-1 h-px bg-slate-200" />}
            <div className="flex items-center gap-2 shrink-0">
              <span className={`w-6 h-6 rounded-full text-xs font-black flex items-center justify-center ${circleCls}`}>{num}</span>
              <span className={`text-xs font-bold ${textCls} hidden sm:block`}>{label}</span>
            </div>
          </React.Fragment>
        ))}
      </div>

      <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-4 flex gap-3">
        <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-black text-amber-800">Review your resume before applying</p>
          <p className="text-xs font-medium text-amber-700 mt-1">
            Make sure your resume is tailored for <strong>{job.title}</strong> at <strong>{job.company}</strong>.
          </p>
        </div>
      </div>

      <div className="border-2 border-slate-200 rounded-2xl p-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center border border-emerald-100">
            <FileText className="w-6 h-6 text-emerald-600" />
          </div>
          <div>
            <p className="font-black text-slate-900 text-sm">AI Optimized Resume</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {taskId ? 'Latest analysis — ready to submit' : 'No resume analyzed yet'}
            </p>
          </div>
        </div>
        <button onClick={previewResume} disabled={previewing || !taskId}
          className="px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest bg-slate-900 text-white hover:bg-emerald-600 transition-all disabled:bg-slate-200 disabled:text-slate-400 flex items-center gap-2 shrink-0">
          <ExternalLink className="w-3.5 h-3.5" />
          {previewing ? 'Opening...' : 'Preview PDF'}
        </button>
      </div>

      {!taskId && (
        <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 text-center">
          <p className="text-sm font-bold text-slate-600">No optimized resume yet</p>
          <p className="text-xs text-slate-400 mt-1">Use the <strong>AI Resume Optimizer</strong> above first. You can still apply without it.</p>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button onClick={onBack} className="flex-1 py-3.5 rounded-2xl font-black text-sm uppercase tracking-widest bg-slate-100 text-slate-600 hover:bg-slate-200 transition-all">
          ← Back
        </button>
        <button onClick={onConfirm} disabled={applying}
          className="flex-1 py-3.5 rounded-2xl font-black text-sm uppercase tracking-widest bg-emerald-600 text-white hover:bg-emerald-500 transition-all disabled:bg-slate-300 flex items-center justify-center gap-2 active:scale-[0.98]">
          <Send className="w-4 h-4" />
          {applying ? 'Submitting...' : 'Confirm & Apply'}
        </button>
      </div>
    </div>
  );
}

// ── Job Detail Modal ──────────────────────────────────────────────────────────
function JobModal({ job, onClose, onApply, lastTaskId }) {
  const [step, setStep]     = useState('details');
  const [applying, setApplying] = useState(false);
  const wt = workType(job.location, job.work_type);

  const handleConfirmApply = async () => {
    setApplying(true);
    try {
      await onApply(job.id, job.url);
      setStep('done');
    } catch (e) {
      alert(e?.response?.data?.detail || 'Failed to apply. Please try again.');
    } finally { setApplying(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-t-3xl p-6 text-white shrink-0 overflow-hidden">
          <TechGridBg />
          <button onClick={onClose}
            className="absolute top-4 right-4 w-9 h-9 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-all z-10">
            <X className="w-4 h-4" />
          </button>
          <div className="flex items-start gap-4 relative z-10">
            <Logo company={job.company} />
            <div className="flex-1 min-w-0 pr-8">
              <h2 className="text-lg font-black leading-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
                {job.title}
              </h2>
              <p className="text-emerald-400 font-bold text-sm mt-0.5">{job.company}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${wt.cls}`}>{wt.label}</span>
                {job.location && (
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-white/10 text-white/80 border border-white/10">
                    📍 {job.location}
                  </span>
                )}
                {job.salary_range
                  ? <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/20">💰 {job.salary_range}</span>
                  : <span className="text-xs px-2.5 py-1 rounded-full bg-white/5 text-white/40 border border-white/10">💰 Not disclosed</span>
                }
                {job.source && (
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${sourceColor(job.source)}`}>
                    {job.source}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1">
          {step === 'details' && (
            <div className="p-7 space-y-5">
              <div>
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-3">Job Description</h3>
                <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100 max-h-72 overflow-y-auto">
                  <p className="text-sm font-medium text-slate-700 leading-relaxed whitespace-pre-line">
                    {job.description || 'No description available. Click "View Original" to see the full posting.'}
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setStep('review')}
                  className="flex-1 py-3.5 rounded-2xl font-black text-sm uppercase tracking-widest bg-slate-900 text-white hover:bg-emerald-600 transition-all flex items-center justify-center gap-2 active:scale-[0.98]">
                  <Send className="w-4 h-4" /> Apply for This Role →
                </button>
                {job.url && (
                  <a href={job.url} target="_blank" rel="noopener noreferrer"
                    className="px-5 py-3.5 rounded-2xl font-bold text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 transition-all flex items-center gap-2 shrink-0">
                    <ExternalLink className="w-4 h-4" /> Original
                  </a>
                )}
              </div>
            </div>
          )}

          {step === 'review' && (
            <ResumeReviewStep job={job} taskId={lastTaskId}
              onConfirm={handleConfirmApply} onBack={() => setStep('details')} applying={applying} />
          )}

          {step === 'done' && (
            <div className="p-10 text-center">
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-emerald-600" />
              </div>
              <h3 className="text-xl font-black text-slate-900 mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>
                Application Submitted!
              </h3>
              <p className="text-slate-500 text-sm mb-1">
                You've applied for <strong className="text-slate-800">{job.title}</strong> at <strong className="text-slate-800">{job.company}</strong>.
              </p>
              <p className="text-slate-400 text-xs mb-6">A confirmation email has been sent. Track it in your dashboard.</p>
              <button onClick={onClose}
                className="px-8 py-3 rounded-2xl font-black text-sm uppercase tracking-widest bg-slate-900 text-white hover:bg-emerald-600 transition-all">
                Back to Jobs
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────
function Pagination({ current, total, onChange }) {
  const pages = Math.ceil(total / JOBS_PER_PAGE);
  if (pages <= 1) return null;

  // Show at most 5 page numbers centered around current
  const range = [];
  const delta = 2;
  for (let i = Math.max(1, current - delta); i <= Math.min(pages, current + delta); i++) {
    range.push(i);
  }

  return (
    <div className="flex items-center justify-center gap-2 mt-10">
      <button onClick={() => onChange(current - 1)} disabled={current === 1}
        className="flex items-center gap-1 px-4 py-2.5 rounded-xl font-black text-xs uppercase tracking-widest border-2 border-slate-800 text-slate-400 hover:border-emerald-500 hover:text-emerald-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all bg-slate-900">
        <ChevronLeft className="w-3.5 h-3.5" /> Prev
      </button>

      {range[0] > 1 && (
        <>
          <button onClick={() => onChange(1)}
            className="w-10 h-10 rounded-xl font-black text-xs border-2 border-slate-800 text-slate-400 hover:border-emerald-500 hover:text-emerald-400 transition-all bg-slate-900">
            1
          </button>
          {range[0] > 2 && <span className="text-slate-600 font-bold">···</span>}
        </>
      )}

      {range.map(p => (
        <button key={p} onClick={() => onChange(p)}
          className={`w-10 h-10 rounded-xl font-black text-xs border-2 transition-all ${
            p === current
              ? 'bg-emerald-600 border-emerald-600 text-white shadow-lg shadow-emerald-600/20'
              : 'border-slate-800 text-slate-400 hover:border-emerald-500 hover:text-emerald-400 bg-slate-900'
          }`}>
          {p}
        </button>
      ))}

      {range[range.length - 1] < pages && (
        <>
          {range[range.length - 1] < pages - 1 && <span className="text-slate-600 font-bold">···</span>}
          <button onClick={() => onChange(pages)}
            className="w-10 h-10 rounded-xl font-black text-xs border-2 border-slate-800 text-slate-400 hover:border-emerald-500 hover:text-emerald-400 transition-all bg-slate-900">
            {pages}
          </button>
        </>
      )}

      <button onClick={() => onChange(current + 1)} disabled={current === pages}
        className="flex items-center gap-1 px-4 py-2.5 rounded-xl font-black text-xs uppercase tracking-widest border-2 border-slate-800 text-slate-400 hover:border-emerald-500 hover:text-emerald-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all bg-slate-900">
        Next <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// ── Main JobFeed ──────────────────────────────────────────────────────────────
export default function JobFeed({ jobs, onApply, lastTaskId }) {
  const [selected, setSelected] = useState(null);
  const [page, setPage]         = useState(1);
  const safeJobs = Array.isArray(jobs) ? jobs : [];

  // Reset to page 1 when jobs list changes (filter/search)
  React.useEffect(() => { setPage(1); }, [jobs]);

  const start    = (page - 1) * JOBS_PER_PAGE;
  const pageJobs = safeJobs.slice(start, start + JOBS_PER_PAGE);

  const handlePageChange = (p) => {
    setPage(p);
    // Scroll to job feed section smoothly
    document.getElementById('job-feed-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (safeJobs.length === 0) return (
    <div className="bg-slate-900 border-2 border-dashed border-slate-800 p-14 rounded-3xl text-center mt-6"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="text-5xl mb-4 opacity-30">🌍</div>
      <p className="text-slate-400 font-bold text-base">No jobs found for this filter.</p>
      <p className="text-slate-500 text-sm font-medium mt-1">Try a different country or search term.</p>
    </div>
  );

  return (
    <>
      {selected && (
        <JobModal job={selected} onClose={() => setSelected(null)}
          onApply={onApply} lastTaskId={lastTaskId} />
      )}

      {/* Scroll anchor */}
      <div id="job-feed-top" style={{ scrollMarginTop: '80px' }} />

      {/* Results count */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">
          Showing {start + 1}–{Math.min(start + JOBS_PER_PAGE, safeJobs.length)} of{' '}
          <span className="text-emerald-400">{safeJobs.length}</span> roles
        </p>
        <p className="text-xs font-bold text-slate-600">
          Page {page} of {Math.ceil(safeJobs.length / JOBS_PER_PAGE)}
        </p>
      </div>

      {/* Job cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {pageJobs.map((job) => {
          const wt = workType(job.location, job.work_type);
          return (
            <div key={job.id}
              className="relative bg-slate-900 rounded-3xl border-2 border-slate-800 hover:border-emerald-500/50 hover:shadow-2xl hover:shadow-emerald-900/20 transition-all group flex flex-col overflow-hidden cursor-pointer"
              onClick={() => setSelected(job)}>

              {/* Tech grid background */}
              <TechGridBg />

              {/* Top accent line */}
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent group-hover:via-emerald-500 transition-all" />

              <div className="relative z-10 p-6 flex-1">
                {/* Company + title */}
                <div className="flex items-start gap-3 mb-4">
                  <Logo company={job.company} />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-black text-white text-sm leading-tight group-hover:text-emerald-400 transition-colors line-clamp-2">
                      {job.title || 'Technical Role'}
                    </h3>
                    <p className="text-slate-400 text-xs font-bold mt-0.5 truncate">{job.company || 'Company'}</p>
                  </div>
                  <span className={`text-[10px] font-black px-2 py-1 rounded-full border shrink-0 ${wt.cls}`}>
                    {wt.label}
                  </span>
                </div>

                {/* Salary */}
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  <span className="text-xs font-bold text-slate-300">
                    {job.salary_range || <span className="text-slate-600 font-normal italic">Not disclosed</span>}
                  </span>
                </div>

                {/* Location */}
                <div className="flex items-center gap-2 mb-4">
                  <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span className="text-xs font-semibold text-slate-400 truncate">
                    {job.location || 'Remote / Global'}
                  </span>
                </div>

                {/* Description preview */}
                {job.description && (
                  <p className="text-xs font-medium text-slate-500 leading-relaxed line-clamp-3">
                    {job.description}
                  </p>
                )}

                {/* Source + category badges */}
                <div className="flex flex-wrap gap-1.5 mt-4">
                  {job.source && (
                    <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${sourceColor(job.source)}`}>
                      {job.source}
                    </span>
                  )}
                  {job.category && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                      {job.category}
                    </span>
                  )}
                </div>
              </div>

              {/* CTA */}
              <div className="relative z-10 px-6 pb-6">
                <div className="w-full py-3 rounded-2xl text-xs font-black uppercase tracking-widest bg-slate-800 text-slate-300 group-hover:bg-emerald-600 group-hover:text-white transition-all flex items-center justify-center gap-2 border border-slate-700 group-hover:border-emerald-600">
                  <FileText className="w-3.5 h-3.5" /> View Details & Apply
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      <Pagination current={page} total={safeJobs.length} onChange={handlePageChange} />
    </>
  );
}
