import React from 'react';
import { Briefcase, MapPin, DollarSign, Send } from 'lucide-react';

export default function JobFeed({ jobs, onApply }) {
  // ARRAY GUARD: Critical to prevent "TypeError: e.map is not a function"
  const safeJobs = Array.isArray(jobs) ? jobs : [];

  if (safeJobs.length === 0) {
    return (
      <div className="bg-white p-12 rounded-3xl border border-dashed border-slate-200 text-center mt-8">
        <div className="text-4xl mb-4 opacity-20">🔍</div>
        <p className="text-slate-400 font-medium italic">
          No live jobs found in your region. Check back soon for AI-matched opportunities.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
      {safeJobs.map((job) => (
        <div 
          key={job.id || Math.random()} 
          className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 hover:border-blue-200 hover:shadow-xl hover:shadow-blue-900/5 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                <h3 className="font-bold text-lg text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1">
                  {job.title || "Technical Role"}
                </h3>
                <p className="text-blue-600 font-bold text-sm uppercase tracking-tight">
                  {job.company || "Stealth Startup"}
                </p>
              </div>
              <span className="bg-slate-100 text-slate-500 text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-lg border border-slate-200">
                {job.source || 'Engine'}
              </span>
            </div>

            <div className="space-y-3 mb-8">
              <div className="flex items-center text-slate-500 text-sm font-medium">
                <div className="w-8 h-8 bg-slate-50 rounded-lg flex items-center justify-center mr-3">
                  <MapPin className="w-4 h-4 text-slate-400" />
                </div>
                {job.location || 'Remote / Global'}
              </div>
              <div className="flex items-center text-slate-500 text-sm font-medium">
                <div className="w-8 h-8 bg-slate-50 rounded-lg flex items-center justify-center mr-3">
                  <DollarSign className="w-4 h-4 text-slate-400" />
                </div>
                {job.salary_range || 'Competitive Pay'}
              </div>
            </div>
          </div>

          <button
            onClick={() => onApply && onApply(job.id)}
            className="w-full bg-slate-900 hover:bg-blue-600 text-white py-4 rounded-2xl font-black uppercase tracking-widest flex items-center justify-center transition-all active:scale-[0.98] shadow-lg shadow-slate-900/10 hover:shadow-blue-600/20"
          >
            <Send className="w-4 h-4 mr-2" /> 
            Quick Apply
          </button>
        </div>
      ))}
    </div>
  );
}
