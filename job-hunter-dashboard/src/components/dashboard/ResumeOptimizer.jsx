import React from 'react';

export default function ResumeOptimizer({ missingKeywords, jobTitle }) {
  // Simple logic to generate suggestions on the fly or fetch from backend
  const generateFix = (skill) => {
    const verbs = ["Spearheaded", "Optimized", "Architected", "Engineered"];
    const verb = verbs[Math.floor(Math.random() * verbs.length)];
    return `${verb} ${skill} integration to enhance workflow efficiency and scalability.`;
  };

  if (!missingKeywords || missingKeywords.length === 0) return null;

  return (
    <div className="mt-8 bg-emerald-50 border border-emerald-100 rounded-2xl p-6 animate-in slide-in-from-bottom duration-500">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">✨</span>
        <h3 className="text-lg font-bold text-emerald-900">AI Resume Fixer</h3>
      </div>
      
      <p className="text-emerald-700 text-sm mb-4">
        Add these bullet points to your resume to close the gap for the <span className="font-bold">{jobTitle}</span> role:
      </p>

      <div className="space-y-3">
        {missingKeywords.map((skill, index) => (
          <div key={index} className="bg-white p-4 rounded-xl border border-emerald-200 shadow-sm group">
            <div className="flex justify-between items-start mb-1">
              <span className="text-xs font-bold uppercase tracking-widest text-emerald-500">Missing: {skill}</span>
              <button 
                onClick={() => navigator.clipboard.writeText(generateFix(skill))}
                className="text-xs text-slate-400 hover:text-emerald-600 font-bold transition-colors"
              >
                📋 Copy
              </button>
            </div>
            <p className="text-slate-700 text-sm italic">"{generateFix(skill)}"</p>
          </div>
        ))}
      </div>
    </div>
  );
}
