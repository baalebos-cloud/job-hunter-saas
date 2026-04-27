import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://baalebo.xyz/api/v1";

function ScoreCircle({ score }) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (circumference * score) / 100;
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444';
  const label = score >= 80 ? 'Strong Fit' : score >= 60 ? 'Good Fit' : 'Needs Work';

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-36 h-36">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 144 144">
          <circle cx="72" cy="72" r={radius} stroke="#e2e8f0" strokeWidth="10" fill="none" />
          <circle
            cx="72" cy="72" r={radius}
            stroke={color} strokeWidth="10" fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1.2s ease-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-black text-slate-900">{Math.round(score)}%</span>
        </div>
      </div>
      <span className="mt-2 text-xs font-black uppercase tracking-widest px-3 py-1 rounded-full"
        style={{ backgroundColor: `${color}20`, color }}>
        {label}
      </span>
    </div>
  );
}

function StatBox({ label, value, color }) {
  return (
    <div className="text-center">
      <div className={`text-3xl font-black ${color}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold mt-1">{label}</div>
    </div>
  );
}

function QuickWin({ number, text, color }) {
  const colors = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
    purple: 'bg-purple-50 text-purple-700 border-purple-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
  };
  const numColors = {
    emerald: 'bg-emerald-500', blue: 'bg-blue-500',
    purple: 'bg-purple-500', amber: 'bg-amber-500',
  };
  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl border ${colors[color]}`}>
      <span className={`${numColors[color]} text-white text-xs font-black w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5`}>
        {number}
      </span>
      <p className="text-xs leading-relaxed font-medium">{text}</p>
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
        <span className="text-xs font-bold text-slate-400">{score}% ({count} found)</span>
      </div>
      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${score}%`, backgroundColor: score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444' }} />
      </div>
    </div>
  );
}

function JobCard({ job, onApply }) {
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const handleApply = async () => {
    setApplying(true);
    try { await onApply(job.id); setApplied(true); }
    catch { alert('Failed to apply. Please try again.'); }
    finally { setApplying(false); }
  };

  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-5 hover:border-emerald-200 hover:shadow-lg hover:shadow-emerald-900/5 transition-all group">
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <h4 className="font-bold text-slate-900 text-sm group-hover:text-emerald-600 transition-colors line-clamp-1">
            {job.title}
          </h4>
          <p className="text-emerald-600 font-bold text-xs uppercase tracking-tight mt-0.5">
            {job.company || 'Top Company'}
          </p>
        </div>
        {job.match_score && (
          <span className="text-[10px] font-black px-2 py-1 rounded-lg bg-emerald-50 text-emerald-600 ml-2 shrink-0">
            {job.match_score}% match
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-400 mb-4">
        <span>📍 {job.location || 'Remote'}</span>
        <span>💰 {job.salary_range || 'Competitive'}</span>
      </div>
      <button
        onClick={handleApply}
        disabled={applying || applied}
        className={`w-full py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
          applied ? 'bg-emerald-50 text-emerald-600 cursor-default'
          : 'bg-slate-900 text-white hover:bg-emerald-600 active:scale-[0.98]'
        }`}
      >
        {applied ? '✓ Applied' : applying ? 'Applying...' : 'Quick Apply →'}
      </button>
    </div>
  );
}

function FaqSection() {
  const [open, setOpen] = useState(null);
  const faqs = [
    { q: 'What is an ATS and why does it matter?', a: 'An Applicant Tracking System filters resumes automatically before a human sees them. If your resume lacks the right keywords, it gets rejected instantly — regardless of your qualifications.' },
    { q: 'How does Baalebos scan my resume?', a: 'Our AI extracts text from your resume, compares it against the job description you provided, and scores it across action verbs, technical skills, and soft skills using NLP keyword matching.' },
    { q: 'Is Baalebos free?', a: 'Yes — the ATS analysis and PDF download are completely free. Premium features like unlimited scans, cover letter generation, and direct recruiter outreach will be available in future plans.' },
    { q: 'Is my resume stored or shared?', a: 'Your resume is processed securely and only used to generate your analysis. We do not share your data with third parties.' },
    { q: 'What file formats are supported?', a: 'We support PDF, DOCX, and DOC file formats. For best results, use a clean single-column PDF.' },
    { q: 'How do I improve my ATS score?', a: 'Add the missing keywords naturally into your resume, quantify achievements with numbers, use strong action verbs, and mirror the exact language from the job description.' },
  ];
  return (
    <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
      <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-6">Frequently Asked Questions</h3>
      <div className="space-y-2">
        {faqs.map((faq, i) => (
          <div key={i} className="border border-slate-100 rounded-2xl overflow-hidden">
            <button onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex justify-between items-center p-4 text-left hover:bg-slate-50 transition-colors">
              <span className="text-sm font-bold text-slate-800">{faq.q}</span>
              <span className="text-slate-400 ml-4 shrink-0">{open === i ? '−' : '+'}</span>
            </button>
            {open === i && (
              <div className="px-4 pb-4 text-sm text-slate-500 leading-relaxed border-t border-slate-50">{faq.a}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AtsResultView({ data }) {
  const [matchedJobs, setMatchedJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const token = localStorage.getItem("token");
  const {
    overall_score = 0, keywords_matched = 0, keywords_missing = 0,
    total_keywords = 0, breakdown = {}, missing_list = [],
    job_title = 'Target Role', resume_id,
  } = data || {};

  useEffect(() => {
    if (!token) return;
    const fetchMatchedJobs = async () => {
      setLoadingJobs(true);
      try {
        // Try the matched endpoint first (uses user's track + pasted JD keywords)
        const res = await axios.get(`${API_BASE_URL}/jobs/matched`, {
          headers: { Authorization: `Bearer ${token}` },
          params: { job_title, limit: 6 }
        });
        setMatchedJobs(Array.isArray(res.data) ? res.data : []);
      } catch {
        // Fallback: fetch all jobs from DB
        try {
          const fallback = await axios.get(`${API_BASE_URL}/jobs/`);
          setMatchedJobs(Array.isArray(fallback.data) ? fallback.data.slice(0, 6) : []);
        } catch { /* silent */ }
      } finally {
        setLoadingJobs(false);
      }
    };
    fetchMatchedJobs();
  }, [token, job_title]);

  const handleApply = async (jobId) => {
    if (!token) { window.location.href = '/login'; return; }
    await axios.post(`${API_BASE_URL}/jobs/${jobId}/apply`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
  };

  const handleDownload = async () => {
    if (!token) { window.location.href = '/signup'; return; }
    setDownloading(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/resume/download/${resume_id}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Baalebos_Optimized_${job_title}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setDownloaded(true);
    } catch {
      alert('Resume is still being generated. Please wait a moment and try again.');
    } finally {
      setDownloading(false);
    }
  };

  const scoreTip = overall_score >= 80
    ? 'Your resume matches well. Focus on quantifying achievements to stand out further.'
    : overall_score >= 60
    ? 'Good foundation. Adding the missing keywords below will significantly boost your score.'
    : 'Your resume needs more alignment with the job requirements. Use the Quick Wins below.';

  if (!data) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">

      {/* ATS Score */}
      <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
        <h2 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-6">Your ATS Match Score</h2>
        <div className="flex flex-col md:flex-row items-center gap-8">
          <ScoreCircle score={overall_score} />
          <div className="flex-1 space-y-4">
            <p className="text-slate-600 text-sm leading-relaxed">
              Your resume scored <span className="font-black text-slate-900">{Math.round(overall_score)}%</span> match
              on <span className="font-black text-slate-900">{job_title}</span>. {scoreTip}
            </p>
            <div className="flex gap-8 pt-2 border-t border-slate-100">
              <StatBox label="Keywords Matched" value={keywords_matched} color="text-emerald-600" />
              <StatBox label="Keywords Missing" value={keywords_missing} color="text-rose-500" />
              <StatBox label="Total Keywords" value={total_keywords} color="text-slate-700" />
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                <span>Needs Work</span><span>Strong Fit</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-1000"
                  style={{ width: `${overall_score}%`, backgroundColor: overall_score >= 80 ? '#10b981' : overall_score >= 60 ? '#f59e0b' : '#ef4444' }} />
              </div>
            </div>
            <div className="flex items-start gap-2 bg-emerald-50 rounded-xl p-3">
              <span className="text-emerald-500 text-sm mt-0.5">💡</span>
              <p className="text-emerald-700 text-xs font-medium">
                <span className="font-black">Tip:</span> Adding the missing keywords below could improve your ATS score by up to{' '}
                <span className="font-black">{Math.min(30, Math.round((keywords_missing / Math.max(total_keywords, 1)) * 100))}%</span>.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Top Keywords */}
      {missing_list?.length > 0 && (
        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
          <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-1">Top Keywords to Add</h3>
          <p className="text-slate-500 text-xs mb-5">These missing keywords are hurting your score — adding them could significantly improve your ATS match.</p>
          <div className="flex flex-wrap gap-2">
            {missing_list.slice(0, 12).map((kw, i) => (
              <span key={i} className="px-3 py-1.5 rounded-lg text-xs font-bold border"
                style={{ backgroundColor: i < 3 ? '#fef3c7' : '#f8fafc', borderColor: i < 3 ? '#fcd34d' : '#e2e8f0', color: i < 3 ? '#92400e' : '#475569' }}>
                {typeof kw === 'string' ? kw : kw.skill || kw}
                {i < 3 && <span className="ml-1 text-amber-500">★</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Quick Wins */}
      {breakdown && Object.keys(breakdown).length > 0 && (
        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
          <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-1">Quick Wins</h3>
          <p className="text-slate-500 text-xs mb-5">These are the fastest changes you can make right now to improve your resume.</p>
          <div className="space-y-3">
            {breakdown.action_verbs && <QuickWin number={1} color="emerald" text={`Strengthen action verbs — your resume scores ${breakdown.action_verbs.score}% here. Aim for 80%+ by replacing weak verbs with impact words like "Architected", "Spearheaded", "Engineered".`} />}
            {missing_list?.[0] && <QuickWin number={2} color="blue" text={`Add "${missing_list[0]}" and "${missing_list[1] || 'related skills'}" to your skills section — weave them into bullet points that match the job requirements naturally.`} />}
            {breakdown.soft_skills && <QuickWin number={3} color="purple" text={`Quantify impact: add specific numbers to your achievements (e.g. "led team of 12", "reduced processing time by 40%") to demonstrate business value.`} />}
            {job_title && <QuickWin number={4} color="amber" text={`Mirror the job title "${job_title}" in your resume summary/headline — ATS systems heavily weight title-to-title matches.`} />}
          </div>
        </div>
      )}

      {/* Category Breakdown */}
      {breakdown && Object.keys(breakdown).length > 0 && (
        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
          <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-6">📊 Category Breakdown</h3>
          <div className="space-y-5">
            {breakdown.action_verbs && <CategoryBar label="Action Verbs" icon="⚡" score={breakdown.action_verbs.score} count={breakdown.action_verbs.count} />}
            {breakdown.technical_skills && <CategoryBar label="Technical Skills" icon="💻" score={breakdown.technical_skills.score} count={breakdown.technical_skills.count} />}
            {breakdown.soft_skills && <CategoryBar label="Soft Skills" icon="🤝" score={breakdown.soft_skills.score} count={breakdown.soft_skills.count} />}
          </div>
        </div>
      )}

      {/* Free Download */}
      <div className="bg-slate-900 rounded-3xl p-8 text-white">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <p className="text-[10px] font-black uppercase tracking-widest text-emerald-400 mb-1">Free Download</p>
            <h3 className="text-xl font-black tracking-tight">Download Your Optimized Resume PDF</h3>
            <p className="text-slate-400 text-sm mt-1">
              {token ? 'Your AI-optimized resume is ready. Download it free — no payment required.'
                : 'Create a free account to download your AI-optimized resume instantly.'}
            </p>
          </div>
          <button onClick={handleDownload} disabled={downloading || downloaded}
            className={`shrink-0 px-8 py-4 rounded-2xl font-black uppercase tracking-widest text-xs transition-all ${
              downloaded ? 'bg-emerald-500 text-white cursor-default'
              : 'bg-emerald-500 hover:bg-emerald-400 text-white active:scale-[0.98] shadow-xl shadow-emerald-900/30'
            }`}>
            {downloaded ? '✓ Downloaded' : downloading ? 'Preparing...' : '📥 Download Free PDF'}
          </button>
        </div>
      </div>

      {/* AI-Matched Jobs */}
      <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
        <div className="mb-6">
          <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-1">AI-Matched Jobs For You</h3>
          <p className="text-slate-500 text-sm">
            Based on your <span className="font-bold text-slate-700">{job_title}</span> track and resume analysis —
            the AI has found roles that match your profile. Apply directly with one click.
          </p>
        </div>

        {!token ? (
          <div className="bg-slate-50 rounded-2xl p-8 text-center border border-dashed border-slate-200">
            <p className="text-slate-500 text-sm mb-4 font-medium">Create a free account to see AI-matched jobs and apply directly.</p>
            <a href="/signup" className="inline-block bg-emerald-600 text-white font-black px-8 py-3 rounded-xl hover:bg-emerald-500 transition-all uppercase tracking-widest text-xs">
              Create Free Account →
            </a>
          </div>
        ) : loadingJobs ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => <div key={i} className="bg-slate-50 rounded-2xl p-5 animate-pulse h-40" />)}
          </div>
        ) : matchedJobs.length === 0 ? (
          <div className="bg-slate-50 rounded-2xl p-8 text-center border border-dashed border-slate-200">
            <div className="text-3xl mb-3 opacity-30">🔍</div>
            <p className="text-slate-400 text-sm font-medium">No matched jobs found for your track yet. Check back soon as new jobs are added daily.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {matchedJobs.map(job => <JobCard key={job.id} job={job} onApply={handleApply} />)}
          </div>
        )}
      </div>

      <FaqSection />
    </div>
  );
}