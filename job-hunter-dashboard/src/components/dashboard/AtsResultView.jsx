import React, { useState } from 'react';
import ResumeOptimizer from './ResumeOptimizer';

export default function AtsResultView({ data }) {
  const [showSignupPrompt, setShowSignupPrompt] = useState(false);

  if (!data) return null;

  const { 
    overall_score, 
    keywords_matched, 
    keywords_missing, 
    total_keywords, 
    breakdown, 
    missing_list,
    job_title,
    resume_id 
  } = data;

  const handleDownloadAttempt = () => {
    // Check if user is logged in (checking for a token in local storage)
    const token = localStorage.getItem("token");
    
    if (!token) {
      setShowSignupPrompt(true);
      // Save the resume ID so we can redirect them back after they sign up
      localStorage.setItem("pending_download_id", resume_id);
    } else {
      // Logic to trigger actual PDF download from backend
      window.location.href = `http://127.0.0.1:8000/resume/download/${resume_id}`;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* 🟢 TOP SECTION: Score & Download Action */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 flex flex-col md:flex-row items-center gap-8 text-center md:text-left">
        <div className="relative flex items-center justify-center">
          <svg className="w-32 h-32 transform -rotate-90">
            <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-100" />
            <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent"
              strokeDasharray={364.4}
              strokeDashoffset={364.4 - (364.4 * overall_score) / 100}
              className="text-emerald-500 transition-all duration-1000 ease-out"
            />
          </svg>
          <span className="absolute text-3xl font-bold text-slate-800">{Math.round(overall_score)}%</span>
        </div>

        <div className="flex-1">
          <h3 className="text-xl font-bold text-slate-900 mb-1">Analysis for {job_title || "Target Role"}</h3>
          <p className="text-slate-500 text-sm mb-4">
            You matched <span className="text-emerald-600 font-bold">{keywords_matched}</span> core competencies.
          </p>
          <button 
            onClick={handleDownloadAttempt}
            className="bg-slate-900 text-white px-6 py-2.5 rounded-xl font-bold text-sm hover:bg-slate-800 transition-all flex items-center gap-2 mx-auto md:mx-0"
          >
            <span>📥</span> Download Improved Resume PDF
          </button>
        </div>
      </div>

      {/* 🛑 MOMENTUM POPUP: Shown only to guests who try to download */}
      {showSignupPrompt && (
        <div className="bg-indigo-600 p-6 rounded-2xl text-white flex flex-col md:flex-row items-center justify-between gap-4 animate-bounce-short">
          <div>
            <h4 className="font-bold text-lg">Ready to apply with this score?</h4>
            <p className="text-indigo-100 text-sm">Create a free account to unlock your AI-optimized PDF and track your applications.</p>
          </div>
          <button 
            className="bg-white text-indigo-600 px-8 py-3 rounded-xl font-bold whitespace-nowrap hover:bg-indigo-50 transition-colors"
            onClick={() => window.location.href = '/signup'}
          >
            Get My PDF Now
          </button>
        </div>
      )}

      {/* ✨ AI FIXER: Suggestions to close the gap */}
      <ResumeOptimizer 
        missingKeywords={missing_list} 
        jobTitle={job_title} 
      />

      {/* 📊 STAT CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatBox label="Keywords Matched" value={keywords_matched} color="text-emerald-600" />
        <StatBox label="Keywords Missing" value={keywords_missing} color="text-rose-500" />
        <StatBox label="Searchable Terms" value={total_keywords} color="text-slate-700" />
      </div>

      {/* 📋 CATEGORY BREAKDOWN */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-2 mb-6">
          <span className="text-xl">📊</span>
          <h3 className="text-lg font-bold text-slate-800">Category Breakdown</h3>
        </div>

        <div className="space-y-6">
          <CategoryBar label="Action Verbs" icon="⚡" score={breakdown.action_verbs.score} count={breakdown.action_verbs.count} />
          <CategoryBar label="Technical Skills" icon="💻" score={breakdown.technical_skills.score} count={breakdown.technical_skills.count} />
          <CategoryBar label="Soft Skills" icon="🤝" score={breakdown.soft_skills.score} count={breakdown.soft_skills.count} />
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 text-center shadow-sm hover:border-slate-200 transition-all">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-xs uppercase tracking-widest text-slate-400 font-bold mt-1">{label}</div>
    </div>
  );
}

function CategoryBar({ label, icon, score, count }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-end">
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className="text-sm font-bold text-slate-700">{label}</span>
        </div>
        <span className="text-xs font-bold text-slate-500">{score}% ({count})</span>
      </div>
      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
        <div className="bg-emerald-500 h-full transition-all duration-1000 ease-in-out" style={{ width: `${score}%` }}></div>
      </div>
    </div>
  );
}
