import { FileText, Target, Briefcase, Clock } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, color }) => (
  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex items-center space-x-4">
    <div className={`p-3 rounded-lg ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <div>
      <p className="text-sm text-slate-500 font-medium">{title}</p>
      <h3 className="text-2xl font-bold text-slate-900">{value ?? '—'}</h3>
    </div>
  </div>
);

export default function StatsGrid({ stats }) {
  if (!stats) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <StatCard title="Total Resumes" value={stats.total_resumes ?? 0} icon={FileText} color="bg-blue-500" />
      <StatCard title="Avg ATS Score" value={`${stats.average_ats_score ?? 0}%`} icon={Target} color="bg-emerald-500" />
      <StatCard title="Total Jobs" value={stats.total_jobs_scraped ?? 0} icon={Briefcase} color="bg-purple-500" />
      <StatCard title="Applications" value={stats.total_applications ?? 0} icon={Clock} color="bg-orange-500" />
    </div>
  );
}
