/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useCallback, useEffect, useState } from 'react';
import { Bell, Briefcase, FileText, Send, Users } from 'lucide-react';
import { adminGet, message, num } from '../adminApi';
import { Banner, SectionHeader, Segmented, Spinner, Stat, card } from '../ui';

export function Bars({ series, color = 'bg-emerald-500', label }) {
  const max = Math.max(1, ...series.map(d => d.count));
  const total = series.reduce((n, d) => n + d.count, 0);
  return (
    <div>
      <div className="flex items-end gap-[3px] h-24" role="img" aria-label={`${label}: ${total} in total`}>
        {series.map(d => (
          <div key={d.date} title={`${d.date}: ${d.count}`} className={`flex-1 rounded-t ${d.count ? color : 'bg-slate-100'}`}
            style={{ height: `${Math.max(4, (100 * d.count) / max)}%` }} />))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-slate-400">
        <span>{series[0]?.date}</span><span>{series[series.length - 1]?.date}</span>
      </div>
    </div>
  );
}

// Product numbers for staff (analytics:read): totals and trends only, no personal data.
export default function AnalyticsTab({ onError }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setData(await adminGet('/console/analytics', { days })); setError(''); }
    catch (err) { if (!onError?.(err)) setError(message(err, 'Product numbers could not be loaded.')); }
  }, [days, onError]);
  useEffect(() => { load(); }, [load]);

  if (error) return <Banner>{error}</Banner>;
  if (!data) return <Spinner />;
  const k = data.kpis;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Job seekers" value={num(k.users)} hint={`+${num(k.users_this_week)} this week · ${num(k.verified_users)} verified`} icon={Users} />
        <Stat label="Resumes tailored" value={num(k.resumes_tailored)} hint={`+${num(k.resumes_this_week)} this week`} icon={FileText} />
        <Stat label="Applications" value={num(k.applications)} hint={`+${num(k.applications_this_week)} this week`} icon={Send} />
        <Stat label="Live jobs" value={num(k.live_jobs)} hint={`+${num(k.new_jobs_this_week)} new this week · ${num(k.employer_jobs)} from employers`} icon={Briefcase} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {[['signups', 'Sign-ups', 'bg-emerald-500'], ['resumes', 'Resumes tailored', 'bg-violet-500'], ['applications', 'Applications', 'bg-sky-500']].map(([key, label, color]) => (
          <section key={key} className={card}>
            <SectionHeader title={label} subtitle={`Per day, last ${data.days} days`}>
              {key === 'signups' && <Segmented value={days} onChange={setDays} options={[[30, '30 days'], [90, '90 days']]} />}
            </SectionHeader>
            <div className="px-5 pb-5"><Bars series={data.daily[key]} color={color} label={label} /></div>
          </section>))}
      </div>
      <p className="text-xs text-slate-500 inline-flex items-center gap-1"><Bell size={12} />{num(k.alert_subscribers)} job seekers receive job alert emails. Staff and employer accounts are not counted.</p>
    </div>
  );
}
