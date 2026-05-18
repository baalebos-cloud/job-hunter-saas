import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const scoreCls = (s) => {
  const n = parseInt(s) || 0;
  if (n >= 85) return 'bg-emerald-100 text-emerald-700 border border-emerald-200';
  if (n >= 60) return 'bg-amber-100 text-amber-700 border border-amber-200';
  return 'bg-rose-100 text-rose-700 border border-rose-200';
};

const statusCls = (s) => {
  switch (s?.toLowerCase()) {
    case 'applied':   return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    case 'messaged':  return 'bg-blue-100 text-blue-700 border-blue-200';
    case 'interview': return 'bg-purple-100 text-purple-700 border-purple-200';
    case 'processed': return 'bg-sky-100 text-sky-700 border-sky-200';
    case 'failed':    return 'bg-rose-100 text-rose-700 border-rose-200';
    default:          return 'bg-slate-100 text-slate-600 border-slate-200';
  }
};

const workType = (loc) => {
  if (!loc) return { label: 'Remote', cls: 'bg-sky-100 text-sky-700 border-sky-200' };
  const l = loc.toLowerCase();
  if (l.includes('hybrid')) return { label: 'Hybrid', cls: 'bg-violet-100 text-violet-700 border-violet-200' };
  if (l.includes('on-site') || l.includes('onsite') || l.includes('office'))
    return { label: 'On-site', cls: 'bg-orange-100 text-orange-700 border-orange-200' };
  return { label: 'Remote', cls: 'bg-sky-100 text-sky-700 border-sky-200' };
};

function Logo({ company, size = 10 }) {
  const slug = (company || 'c').toLowerCase().replace(/[^a-z0-9]/g, '');
  return (
    <img
      src={`https://logo.clearbit.com/${slug}.com`}
      onError={e => { e.target.onerror = null; e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(company || 'C')}&background=0f172a&color=10b981&bold=true&size=80`; }}
      alt={company} className={`w-${size} h-${size} rounded-xl object-contain bg-slate-50 p-0.5 border border-slate-100 shrink-0`}
    />
  );
}

function JobModal({ app, onClose, token }) {
  const job = app?.job || {};
  const wt = workType(job?.location);
  const [msg, setMsg] = useState(
    `Hi ${job?.company || 'Team'},\n\nI recently applied for the ${job?.title || 'role'} position and wanted to introduce myself directly.\n\nI'm a passionate ${job?.category || 'tech'} professional with strong experience in this field. I'd love to discuss how my skills align with your team.\n\nBest regards`
  );
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [copied, setCopied] = useState(false);
  const [msgError, setMsgError] = useState('');

  const sendMessage = async () => {
    if (!msg.trim()) return;
    setSending(true); setMsgError('');
    try {
      await axios.post(`${API_BASE_URL}/jobs/${job?.id}/message`,
        { message: msg },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setSent(true);
    } catch (e) {
      setMsgError(e.response?.data?.detail || 'Failed to send. Please try again.');
    } finally {
      setSending(false);
    }
  };

  const copy = () => { navigator.clipboard.writeText(msg); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm"
      style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto">

        {/* Header */}
        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-t-3xl p-7 text-white relative">
          <button onClick={onClose}
            className="absolute top-4 right-4 w-9 h-9 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-all text-xl font-bold">
            ×
          </button>
          <div className="flex items-start gap-4">
            <Logo company={job?.company} size={14} />
            <div>
              <h2 className="text-xl font-black leading-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
                {job?.title || `Application #${app?.job_id}`}
              </h2>
              <p className="text-emerald-400 font-bold text-sm mt-1">{job?.company}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                <span className={`text-xs font-bold px-3 py-1 rounded-full border ${wt.cls}`}>{wt.label}</span>
                {job?.location && <span className="text-xs font-semibold px-3 py-1 rounded-full bg-white/10 text-white/80 border border-white/10">📍 {job.location}</span>}
                {job?.salary_range
                  ? <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/20">💰 {job.salary_range}</span>
                  : <span className="text-xs px-3 py-1 rounded-full bg-white/5 text-white/40 border border-white/10">💰 Salary not disclosed</span>
                }
              </div>
            </div>
          </div>
        </div>

        <div className="p-7 space-y-6">
          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'ATS Match', val: <span className={`text-base font-black px-3 py-1 rounded-full ${scoreCls(app?.ats_score)}`}>{app?.ats_score || 0}%</span> },
              { label: 'Status', val: <span className={`text-xs font-black uppercase tracking-wide px-3 py-1 rounded-lg border ${statusCls(app?.status)}`}>{app?.status || 'Pending'}</span> },
              { label: 'Work Type', val: <span className={`text-xs font-bold px-3 py-1 rounded-full border ${wt.cls}`}>{wt.label}</span> },
            ].map(({ label, val }) => (
              <div key={label} className="bg-slate-50 rounded-2xl p-4 text-center border border-slate-100">
                <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">{label}</p>
                {val}
              </div>
            ))}
          </div>

          {/* Description */}
          {job?.description && (
            <div>
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-3">Job Description</h3>
              <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100 max-h-48 overflow-y-auto">
                <p className="text-sm font-medium text-slate-700 leading-relaxed whitespace-pre-line">{job.description}</p>
              </div>
            </div>
          )}

          {/* HR Message */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <div>
                <h3 className="text-sm font-black text-slate-900">📨 Send Direct Message to HR</h3>
                <p className="text-xs font-medium text-slate-400 mt-0.5">Message is tracked in your dashboard after sending.</p>
              </div>
              <button onClick={copy}
                className={`text-xs font-black px-3 py-1.5 rounded-xl transition-all ${copied ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            </div>

            {sent ? (
              <div className="bg-emerald-50 border-2 border-emerald-200 rounded-2xl p-5 text-center">
                <p className="text-2xl mb-2">✅</p>
                <p className="text-emerald-700 font-black text-sm">Message sent & tracked!</p>
                <p className="text-emerald-600 text-xs font-medium mt-1">Your status has been updated to "Messaged". A confirmation email has been sent to you.</p>
              </div>
            ) : (
              <>
                <textarea rows={7} value={msg} onChange={e => setMsg(e.target.value)}
                  className="w-full p-4 rounded-2xl border-2 border-slate-200 bg-slate-50 text-sm font-medium text-slate-800 leading-relaxed resize-none outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200 transition-all" />
                {msgError && <p className="text-rose-600 text-xs font-bold mt-2">⚠️ {msgError}</p>}
                <button onClick={sendMessage} disabled={sending}
                  className="w-full mt-3 py-3.5 rounded-2xl font-black text-sm uppercase tracking-widest bg-slate-900 text-white hover:bg-emerald-600 transition-all disabled:bg-slate-300 active:scale-95">
                  {sending ? 'Sending...' : '📤 Send to HR & Track'}
                </button>
              </>
            )}
          </div>

          {/* External link */}
          {job?.url && (
            <a href={job.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full py-3 rounded-2xl border-2 border-slate-200 text-sm font-bold text-slate-600 hover:border-emerald-400 hover:text-emerald-600 transition-all">
              🔗 View Original Job Posting
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ApplicationsTable({ applications, onDelete, token }) {
  const [selected, setSelected] = useState(null);
  const safeApps = Array.isArray(applications) ? applications : [];

  if (safeApps.length === 0) {
    return (
      <div className="bg-white p-14 rounded-3xl border-2 border-dashed border-slate-200 text-center"
        style={{ fontFamily: "'Inter', sans-serif" }}>
        <div className="text-5xl mb-4 opacity-20">📁</div>
        <p className="text-slate-500 font-bold text-base">No applications tracked yet.</p>
        <p className="text-slate-400 text-sm font-medium mt-1">Apply for jobs below to start tracking your progress.</p>
      </div>
    );
  }

  return (
    <>
      {selected && <JobModal app={selected} onClose={() => setSelected(null)} token={token} />}

      <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden"
        style={{ fontFamily: "'Inter', sans-serif" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b-2 border-slate-100">
                {['Role & Company', 'Work Type', 'Salary', 'ATS Match', 'Status', 'Actions'].map(h => (
                  <th key={h} className="px-5 py-4 text-xs font-black uppercase tracking-widest text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {safeApps.map(app => {
                const job = app?.job || {};
                const wt = workType(job?.location);
                return (
                  <tr key={app?.id} className="hover:bg-slate-50/60 transition-colors group">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <Logo company={job?.company} size={10} />
                        <div>
                          <p className="font-black text-slate-900 text-sm leading-tight">
                            {job?.title || `Application #${app?.job_id}`}
                          </p>
                          <p className="text-xs font-semibold text-slate-500 mt-0.5">{job?.company || '—'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`text-xs font-black px-2.5 py-1 rounded-full border ${wt.cls}`}>{wt.label}</span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm font-bold text-slate-800">
                        {job?.salary_range || <span className="text-slate-300 font-normal text-xs italic">Not disclosed</span>}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`text-sm font-black px-3 py-1 rounded-full ${scoreCls(app?.ats_score)}`}>
                        {app?.ats_score || 0}%
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`text-xs font-black uppercase tracking-wide px-2.5 py-1 rounded-lg border ${statusCls(app?.status)}`}>
                        {app?.status || 'Pending'}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <button onClick={() => setSelected(app)}
                          className="text-xs font-black px-3 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 transition-all border border-slate-200">
                          View
                        </button>
                        <button onClick={() => onDelete && onDelete(app?.id)}
                          className="p-2 rounded-xl text-slate-300 hover:text-rose-500 hover:bg-rose-50 transition-all">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}