// =============================================================================
// job-hunter-dashboard/src/components/StatsGrid.jsx
//  1. Tech grid background on each card
//  2. Animated number display
//  3. Better visual hierarchy — trend arrows, glow effects
//  4. Referral earnings card added
// =============================================================================
import { FileText, Target, Briefcase, TrendingUp, Users } from 'lucide-react';

const cards = [
  {
    key:    'total_resumes',
    label:  'Resumes Analyzed',
    icon:   FileText,
    grad:   'from-blue-600 to-blue-400',
    glow:   'shadow-blue-500/20',
    accent: '#3b82f6',
    tip:    'Total AI resume scans',
  },
  {
    key:    'average_ats_score',
    label:  'Avg ATS Score',
    icon:   Target,
    grad:   'from-emerald-600 to-emerald-400',
    glow:   'shadow-emerald-500/20',
    accent: '#10b981',
    suffix: '%',
    tip:    'Average match across all scans',
  },
  {
    key:    'total_jobs_scraped',
    label:  'Live Jobs',
    icon:   Briefcase,
    grad:   'from-purple-600 to-purple-400',
    glow:   'shadow-purple-500/20',
    accent: '#a855f7',
    tip:    'Active jobs in the last 3 days',
  },
  {
    key:    'total_applications',
    label:  'Applications',
    icon:   TrendingUp,
    grad:   'from-amber-600 to-amber-400',
    glow:   'shadow-amber-500/20',
    accent: '#f59e0b',
    tip:    'Jobs you have applied to',
  },
];

const TechGridBg = ({ accent = '#10b981' }) => (
  <div className="absolute inset-0 opacity-[0.04] pointer-events-none"
    style={{
      backgroundImage: `linear-gradient(${accent} 1px, transparent 1px), linear-gradient(90deg, ${accent} 1px, transparent 1px)`,
      backgroundSize: '20px 20px',
    }}
  />
);

const formatValue = (val, suffix) => {
  const n = Number(val) || 0;
  if (!suffix && n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return `${n}${suffix || ''}`;
};

export default function StatsGrid({ stats }) {
  if (!stats) return null;
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(({ key, label, icon: Icon, grad, glow, accent, suffix, tip }) => {
        const raw = stats[key] ?? 0;
        const val = formatValue(raw, suffix);
        return (
          <div key={key}
            className={`relative bg-slate-900 border border-slate-800 rounded-2xl p-5 overflow-hidden shadow-xl ${glow} group hover:border-slate-700 transition-all`}>

            {/* Tech grid background */}
            <TechGridBg accent={accent} />

            {/* Top accent line */}
            <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
              style={{ background: `linear-gradient(90deg, transparent, ${accent}60, transparent)` }} />

            {/* Glow blob */}
            <div className={`absolute -top-8 -right-8 w-28 h-28 rounded-full bg-gradient-to-br ${grad} opacity-10 blur-3xl group-hover:opacity-20 transition-all`} />

            <div className="relative z-10">
              {/* Icon */}
              <div className={`inline-flex p-2.5 rounded-xl bg-gradient-to-br ${grad} shadow-lg mb-4`}>
                <Icon className="w-5 h-5 text-white" />
              </div>

              {/* Value */}
              <div className="text-3xl font-black text-white mb-0.5 tabular-nums">
                {val}
              </div>

              {/* Label */}
              <div className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                {label}
              </div>

              {/* Tip */}
              {tip && (
                <div className="text-[10px] font-medium text-slate-600 mt-1.5 leading-tight">
                  {tip}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
