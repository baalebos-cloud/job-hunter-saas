import React from 'react';

// Helper: Color coding the ATS Score
const getScoreStyle = (score) => {
  const s = parseInt(score) || 0;
  if (s >= 85) return "bg-emerald-50 text-emerald-600 border border-emerald-100";
  if (s >= 60) return "bg-amber-50 text-amber-600 border border-amber-100";
  return "bg-rose-50 text-rose-600 border border-rose-100";
};

// Helper: Color coding the Status
const getStatusStyle = (status) => {
  switch (status?.toLowerCase()) {
    case 'processed': 
    case 'completed': return "bg-blue-50 text-blue-600 border-blue-100";
    case 'applied': return "bg-emerald-50 text-emerald-600 border-emerald-100";
    case 'failed': return "bg-rose-50 text-rose-600 border-rose-100";
    default: return "bg-slate-50 text-slate-500 border-slate-200";
  }
};

export default function ApplicationsTable({ applications, onDelete }) {
  // ARRAY GUARD: Ensure we are dealing with an array to prevent .map crashes
  const safeApps = Array.isArray(applications) ? applications : [];

  if (safeApps.length === 0) {
    return (
      <div className="bg-white p-12 rounded-3xl border border-dashed border-slate-200 text-center">
        <div className="text-4xl mb-4 opacity-20">📁</div>
        <p className="text-slate-400 font-medium italic">
          No applications tracked yet. Start by matching a resume above!
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50/50 border-b border-slate-100">
              <th className="p-5 text-[10px] font-black uppercase tracking-widest text-slate-400">Job Title</th>
              <th className="p-5 text-[10px] font-black uppercase tracking-widest text-slate-400 text-center">ATS Match</th>
              <th className="p-5 text-[10px] font-black uppercase tracking-widest text-slate-400 text-center">Status</th>
              <th className="p-5 text-[10px] font-black uppercase tracking-widest text-slate-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {safeApps.map((app) => (
              <tr key={app.id || Math.random()} className="hover:bg-slate-50/30 transition-colors group">
                <td className="p-5">
                  <div className="font-bold text-slate-800">{app.job_title || "Technical Role"}</div>
                  <div className="text-[10px] font-medium text-slate-400 flex items-center gap-1 mt-0.5">
                    <span className="opacity-50">📄</span> {app.filename || "analysis_result.pdf"}
                  </div>
                </td>

                <td className="p-5 text-center">
                  <span className={`text-xs font-black px-3 py-1.5 rounded-full ${getScoreStyle(app.ats_score)}`}>
                    {app.ats_score || 0}%
                  </span>
                </td>

                <td className="p-5 text-center">
                  <span className={`text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded-lg border shadow-sm ${getStatusStyle(app.status)}`}>
                    {app.status || 'Pending'}
                  </span>
                </td>

                <td className="p-5 text-right">
                  <button
                    onClick={() => onDelete && onDelete(app.id)}
                    className="text-slate-300 hover:text-rose-500 transition-all p-2 bg-slate-50 rounded-xl group-hover:bg-rose-50"
                    title="Withdraw Application"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
