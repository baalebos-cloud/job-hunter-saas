import { FileText, Target, Briefcase, TrendingUp } from 'lucide-react';

const cards = [
  { key: 'total_resumes',      label: 'Resumes Analyzed', icon: FileText,   grad: 'from-blue-600 to-blue-400',    glow: 'shadow-blue-500/20' },
  { key: 'average_ats_score',  label: 'Avg ATS Score',    icon: Target,     grad: 'from-emerald-600 to-emerald-400', glow: 'shadow-emerald-500/20', suffix: '%' },
  { key: 'total_jobs_scraped', label: 'Live Jobs',        icon: Briefcase,  grad: 'from-purple-600 to-purple-400', glow: 'shadow-purple-500/20' },
  { key: 'total_applications', label: 'Applications',     icon: TrendingUp, grad: 'from-amber-600 to-amber-400',  glow: 'shadow-amber-500/20' },
];

export default function StatsGrid({ stats }) {
  if (!stats) return null;
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(({ key, label, icon: Icon, grad, glow, suffix }) => (
        <div key={key}
          className={`relative bg-slate-900 border border-slate-800 rounded-2xl p-5 overflow-hidden shadow-xl ${glow}`}>
          {/* Glow blob */}
          <div className={`absolute -top-6 -right-6 w-24 h-24 rounded-full bg-gradient-to-br ${grad} opacity-20 blur-2xl`} />
          <div className={`inline-flex p-2.5 rounded-xl bg-gradient-to-br ${grad} shadow-lg mb-4`}>
            <Icon className="w-5 h-5 text-white" />
          </div>
          <div className="text-3xl font-black text-white">
            {stats[key] ?? 0}{suffix || ''}
          </div>
          <div className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-1">{label}</div>
        </div>
      ))}
    </div>
  );
}
