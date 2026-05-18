import React from 'react';

export default function ResumeOptimizer({ missingKeywords, jobTitle }) {
  // Simple logic to generate suggestions on the fly or fetch from backend
  const generateFix = (skill) => {
    if (!skill) return 'Add relevant experience to your resume.';
    const verbs = ["Spearheaded", "Optimized", "Architected", "Engineered", "Accelerated", "Enhanced", "Delivered"];
    const verb = verbs[Math.floor(Math.random() * verbs.length)];
    return `${verb} ${skill} integration to enhance workflow efficiency and scalability.`;
  };

  if (!missingKeywords || missingKeywords.length === 0) return null;

  const safeKeywords = Array.isArray(missingKeywords) ? missingKeywords : [];
  const safeJobTitle = jobTitle || 'Target Role';

  return (
    <div className="mt-8 bg-emerald-50 border border-emerald-100 rounded-2xl p-6 animate-in slide-in-from-bottom duration-500">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">✨</span>
        <h3 className="text-lg font-bold text-emerald-900">AI Resume Fixer</h3>
      </div>
      
      <p className="text-emerald-700 text-sm mb-4">
        Add these bullet points to your resume to close the gap for the <span className="font-bold">{safeJobTitle}</span> role:
      </p>

      <div className="space-y-3">
        {safeKeywords.map((skill, index) => {
          const skillStr = typeof skill === 'string' ? skill : skill?.skill || skill?.name || `Skill ${index + 1}`;
          return (
            <div key={`${skillStr}-${index}`} className="bg-white p-4 rounded-xl border border-emerald-200 shadow-sm group">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-bold uppercase tracking-widest text-emerald-500">Missing: {skillStr}</span>
                <button 
                  onClick={() => navigator.clipboard.writeText(generateFix(skillStr))}
                  className="text-xs text-slate-400 hover:text-emerald-600 font-bold transition-colors"
                  title="Copy suggestion to clipboard"
                >
                  📋 Copy
                </button>
              </div>
              <p className="text-slate-700 text-sm italic">"{generateFix(skillStr)}"</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}