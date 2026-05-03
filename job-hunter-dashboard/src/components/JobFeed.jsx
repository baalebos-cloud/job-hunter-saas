import React, { useState } from 'react';
import axios from 'axios';
import { MapPin, DollarSign, Send, X, ExternalLink, FileText, CheckCircle, AlertCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const workType = (loc) => {
  if (!loc) return { label: 'Remote', cls: 'bg-sky-100 text-sky-700 border-sky-200' };
  const l = loc.toLowerCase();
  if (l.includes('hybrid')) return { label: 'Hybrid', cls: 'bg-violet-100 text-violet-700 border-violet-200' };
  if (l.includes('on-site') || l.includes('onsite') || l.includes('office'))
    return { label: 'On-site', cls: 'bg-orange-100 text-orange-700 border-orange-200' };
  return { label: 'Remote', cls: 'bg-sky-100 text-sky-700 border-sky-200' };
};

function Logo({ company }) {
  const slug = (company || 'c').toLowerCase().replace(/[^a-z0-9]/g, '');
  return (
    <img
      src={`https://logo.clearbit.com/${slug}.com`}
      onError={e => { e.target.onerror = null; e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(company || 'C')}&background=0f172a&color=10b981&bold=true&size=80`; }}
      alt={company}
      className="w-12 h-12 rounded-2xl object-contain bg-slate-50 p-1 border border-slate-100 shrink-0"
    />
  );
}

// ── Resume Review Step ────────────────────────────────────────────────────────
function ResumeReviewStep({ job, taskId, onConfirm, onBack, applying }) {
  const token = localStorage.getItem('token');
  const [previewing, setPreviewing] = useState(false);

  const previewResume = async () => {
    if (!token) { window.location.href = '/login'; return; }
    if (!taskId) {
      alert('No optimized resume found. Please run the AI Resume Optimizer first, then apply.');
      return;
    }
    setPreviewing(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/resume/download/${taskId}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      window.open(url, '_blank');
    } catch {
      alert('Resume preview unavailable. You can still apply and download it from your dashboard.');
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="p-7 space-y-5" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Step indicator */}
      <div className="flex items-center gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-emerald-500 text-white text-xs font-black flex items-center justify-center">✓</span>
          <span className="text-xs font-bold text-emerald-600">Job Reviewed</span>
        </div>
        <div className="flex-1 h-px bg-slate-200" />
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-slate-900 text-white text-xs font-black flex items-center justify-center">2</span>
          <span className="text-xs font-black text-slate-900">Review Resume</span>
        </div>
        <div className="flex-1 h-px bg-slate-200" />
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-400 text-xs font-black flex items-center justify-center">3</span>
          <span className="text-xs font-bold text-slate-400">Confirm Apply</span>
        </div>
      </div>

      <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-black text-amber-800">Review your resume before applying</p>
          <p className="text-xs font-medium text-amber-700 mt-1">
            Make sure your optimized resume is tailored for <strong>{job.title}</strong> at <strong>{job.company}</strong> before submitting.
          </p>
        </div>
      </div>

      {/* Resume preview card */}
      <div className="border-2 border-slate-200 rounded-2xl p-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center border border-emerald-100">
            <FileText className="w-6 h-6 text-emerald-600" />
          </div>
          <div>
            <p className="font-black text-slate-900 text-sm">AI Optimized Resume</p>
            <p className="text-xs font-medium text-slate-500 mt-0.5">
              {taskId ? 'Your latest analysis — ready to submit' : 'No resume analyzed yet'}
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
          <p className="text-xs font-medium text-slate-400 mt-1">
            Use the <strong>AI Resume Optimizer</strong> above to analyze your resume first.
            You can still apply without it.
          </p>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button onClick={onBack}
          className="flex-1 py-3.5 rounded-2xl font-black text-sm uppercase tracking-widest bg-slate-100 text-slate-600 hover:bg-slate-200 transition-all">
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
  const [step, setStep] = useState('details'); // 'details' | 'review' | 'done'
  const [applying, setApplying] = useState(false);
  const wt = workType(job.location);

  const handleConfirmApply = async () => {
    setApplying(true);
    try {
      await onApply(job.id, job.url);
      setStep('done');
    } catch (e) {
      alert(e?.response?.data?.detail || 'Failed to apply. Please try again.');
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col">

        {/* Header — always visible */}
        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-t-3xl p-6 text-white relative shrink-0">
          <button onClick={onClose}
            className="absolute top-4 right-4 w-9 h-9 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-all text-xl font-bold">
            <X className="w-4 h-4" />
          </button>
          <div className="flex items-start gap-4">
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
                {job.salary_range ? (
                  <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/20">
                    💰 {job.salary_range}
                  </span>
                ) : (
                  <span className="text-xs px-2.5 py-1 rounded-full bg-white/5 text-white/40 border border-white/10">
                    💰 Salary not disclosed
                  </span>
                )}
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-white/10 text-white/60 border border-white/10">
                  {job.source}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1">

          {step === 'details' && (
            <div className="p-7 space-y-5">
              {/* Full description */}
              <div>
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-3">Full Job Description</h3>
                <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                  <p className="text-sm font-medium text-slate-700 leading-relaxed whitespace-pre-line">
                    {job.description || 'No description available. Click "View Original" to see the full posting.'}
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-1">
                <button onClick={() => setStep('review')}
                  className="flex-1 py-3.5 rounded-2xl font-black text-sm uppercase tracking-widest bg-slate-900 text-white hover:bg-emerald-600 transition-all flex items-center justify-center gap-2 active:scale-[0.98] shadow-lg">
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
            <ResumeReviewStep
              job={job}
              taskId={lastTaskId}
              onConfirm={handleConfirmApply}
              onBack={() => setStep('details')}
              applying={applying}
            />
          )}

          {step === 'done' && (
            <div className="p-10 text-center" style={{ fontFamily: "'Inter', sans-serif" }}>
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-emerald-600" />
              </div>
              <h3 className="text-xl font-black text-slate-900 mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>
                Application Submitted!
              </h3>
              <p className="text-slate-500 font-medium text-sm mb-1">
                You've applied for <strong className="text-slate-800">{job.title}</strong> at <strong className="text-slate-800">{job.company}</strong>.
              </p>
              <p className="text-slate-400 text-xs mb-6">A confirmation email has been sent to you. Track your application in the dashboard.</p>
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

// ── Main JobFeed ──────────────────────────────────────────────────────────────
export default function JobFeed({ jobs, onApply, lastTaskId }) {
  const [selected, setSelected] = useState(null);
  const safeJobs = Array.isArray(jobs) ? jobs : [];

  if (safeJobs.length === 0) {
    return (
      <div className="bg-white p-14 rounded-3xl border-2 border-dashed border-slate-200 text-center mt-8"
        style={{ fontFamily: "'Inter', sans-serif" }}>
        <div className="text-5xl mb-4 opacity-20">🌍</div>
        <p className="text-slate-600 font-bold text-base">No jobs found for this filter.</p>
        <p className="text-slate-400 text-sm font-medium mt-1">Try selecting a different country or check back soon.</p>
      </div>
    );
  }

  return (
    <>
      {selected && (
        <JobModal
          job={selected}
          onClose={() => setSelected(null)}
          onApply={onApply}
          lastTaskId={lastTaskId}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mt-6">
        {safeJobs.map((job) => {
          const wt = workType(job.location);
          return (
            <div key={job.id}
              className="bg-white rounded-3xl border-2 border-slate-100 hover:border-emerald-300 hover:shadow-xl hover:shadow-emerald-900/5 transition-all group flex flex-col overflow-hidden cursor-pointer"
              onClick={() => setSelected(job)}>

              <div className="p-6 flex-1">
                {/* Company + title */}
                <div className="flex items-start gap-3 mb-4">
                  <Logo company={job.company} />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-black text-slate-900 text-base leading-tight group-hover:text-emerald-600 transition-colors"
                      style={{ fontFamily: "'Inter', sans-serif" }}>
                      {job.title || 'Technical Role'}
                    </h3>
                    <p className="text-slate-500 text-sm font-bold mt-0.5 truncate">{job.company || 'Company'}</p>
                  </div>
                  <span className={`text-[10px] font-black px-2.5 py-1 rounded-full border shrink-0 ${wt.cls}`}>
                    {wt.label}
                  </span>
                </div>

                {/* Salary */}
                <div className="flex items-center gap-2.5 mb-2.5">
                  <div className="w-7 h-7 bg-emerald-50 rounded-lg flex items-center justify-center shrink-0">
                    <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
                  </div>
                  <span className="text-sm font-bold text-slate-800">
                    {job.salary_range || <span className="text-slate-300 font-normal italic text-xs">Salary not disclosed</span>}
                  </span>
                </div>

                {/* Location */}
                <div className="flex items-center gap-2.5 mb-4">
                  <div className="w-7 h-7 bg-slate-50 rounded-lg flex items-center justify-center shrink-0">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                  <span className="text-sm font-semibold text-slate-600">{job.location || 'Remote / Global'}</span>
                </div>

                {/* Description preview — 3 lines */}
                {job.description && (
                  <p className="text-sm font-medium text-slate-500 leading-relaxed line-clamp-3">
                    {job.description}
                  </p>
                )}
              </div>

              {/* CTA */}
              <div className="px-6 pb-6">
                <div className="w-full py-3.5 rounded-2xl text-sm font-black uppercase tracking-widest bg-slate-900 text-white group-hover:bg-emerald-600 transition-all flex items-center justify-center gap-2">
                  <FileText className="w-4 h-4" /> View Full Details & Apply
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
