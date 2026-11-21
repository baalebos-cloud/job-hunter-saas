import { Briefcase, Building2, FileText, KeyRound, Send, ShieldAlert, Users, UsersRound } from 'lucide-react';
import { ago, eventTone, num } from '../adminApi';
import { Chip, SectionHeader, Stat, card } from '../ui';

const ATTENTION = {
  suspicious_ips: { icon: ShieldAlert, box: 'bg-rose-50 ring-rose-100', title: 'text-rose-900', detail: 'text-rose-700' },
  pending_employers: { icon: Building2, box: 'bg-amber-50 ring-amber-100', title: 'text-amber-900', detail: 'text-amber-700' },
  duplicates: { icon: UsersRound, box: 'bg-amber-50 ring-amber-100', title: 'text-amber-900', detail: 'text-amber-700' },
  mfa: { icon: KeyRound, box: 'bg-slate-50 ring-slate-100', title: 'text-slate-900', detail: 'text-slate-500' },
};

function GrowthChart({ series }) {
  const width = 640, height = 190, pad = 12;
  const max = Math.max(1, ...series.flatMap(d => [d.signups, d.applications]));
  const x = (i) => pad + (i * (width - pad * 2)) / Math.max(1, series.length - 1);
  const y = (v) => height - pad - (v * (height - pad * 3)) / max;
  const line = (key) => series.map((d, i) => `${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`).join(' ');
  const label = (d) => new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  const totals = series.reduce((acc, d) => ({ s: acc.s + d.signups, a: acc.a + d.applications }), { s: 0, a: 0 });
  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height + 18}`} className="w-full h-56" role="img"
        aria-label={`Last 30 days: ${totals.s} sign-ups and ${totals.a} applications`}>
        {[0.25, 0.5, 0.75, 1].map(f => <line key={f} x1={pad} x2={width - pad} y1={y(max * f)} y2={y(max * f)} stroke="#f1f5f9" />)}
        <line x1={pad} x2={width - pad} y1={y(0)} y2={y(0)} stroke="#e2e8f0" />
        <polyline fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinejoin="round" points={line('applications')} />
        <polyline fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinejoin="round" points={line('signups')} />
        <text x={pad} y={height + 14} fontSize="11" fill="#94a3b8">{max}</text>
        {series.length > 0 && [0, Math.floor(series.length / 2), series.length - 1].map(i => (
          <text key={i} x={x(i)} y={height + 14} fontSize="11" fill="#94a3b8"
            textAnchor={i === 0 ? 'start' : i === series.length - 1 ? 'end' : 'middle'}>{label(series[i])}</text>
        ))}
      </svg>
      <figcaption className="sr-only">Daily sign-ups and applications for the last 30 days.</figcaption>
    </figure>
  );
}

export default function OverviewTab({ data, goTo }) {
  const { kpis, mix, attention, activity, growth } = data;
  const change = kpis.applications_change_pct;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <Stat label="Total users" value={num(kpis.users)} icon={Users} iconTone="text-blue-500"
          hint={`+${num(kpis.users_this_week)} this week · +${num(kpis.users_today)} today`} hintTone="text-emerald-700" />
        <Stat label="Live jobs" value={num(kpis.live_jobs)} icon={Briefcase} iconTone="text-emerald-500"
          hint={`${num(kpis.jobs_today)} added today · ${num(kpis.employer_jobs)} by employers`} />
        <Stat label="Applications" value={num(kpis.applications)} icon={Send} iconTone="text-violet-500"
          hint={change === null ? `${num(kpis.applications_this_week)} this week`
            : `${change >= 0 ? '▲' : '▼'} ${Math.abs(change)}% vs last week`}
          hintTone={change === null ? 'text-slate-500' : change >= 0 ? 'text-emerald-700' : 'text-rose-700'} />
        <Stat label="Resumes generated" value={num(kpis.resumes)} icon={FileText} iconTone="text-amber-500" />
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <div className={`${card} xl:col-span-2`}>
          <SectionHeader title="Growth" subtitle="Last 30 days">
            <span className="flex items-center gap-1.5 text-xs text-slate-500"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />Sign-ups</span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500"><span className="w-2.5 h-2.5 rounded-sm bg-blue-500" />Applications</span>
          </SectionHeader>
          <div className="px-5 pb-4"><GrowthChart series={growth} /></div>
        </div>
        <div className={card}>
          <SectionHeader title="Needs your attention" />
          <ul className="px-5 pb-5 space-y-2.5">
            {attention.length === 0 && <li className="text-sm text-slate-500">All clear. Nothing needs action right now.</li>}
            {attention.map(item => {
              const style = ATTENTION[item.kind] || ATTENTION.mfa;
              const Icon = style.icon;
              return (
                <li key={item.kind}>
                  <button type="button" onClick={() => goTo(item.tab, item.kind)}
                    className={`w-full text-left flex items-start gap-3 p-3 rounded-xl ring-1 hover:brightness-[0.98] ${style.box}`}>
                    <Icon size={18} className={`mt-0.5 shrink-0 ${style.detail}`} />
                    <div className="flex-1 min-w-0">
                      <div className={`text-sm font-medium ${style.title}`}>{item.title}</div>
                      {item.detail && <div className={`text-xs ${style.detail}`}>{item.detail}</div>}
                    </div>
                    <span className={`text-xs font-semibold ${style.detail}`}>{item.kind === 'mfa' ? 'Fix →' : 'Review →'}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <div className={card}>
          <SectionHeader title="Platform mix" />
          <dl className="px-5 pb-5 space-y-3 text-sm">
            {[['Candidates', mix.candidates], ['Employers (approved)', mix.employers_approved], ['Employers (pending)', mix.employers_pending],
              ['Admins', mix.admins], ['Paid plans', mix.paid], ['Suspended accounts', mix.suspended]].map(([label, value]) => (
              <div key={label} className="flex justify-between"><dt className="text-slate-500">{label}</dt><dd className="font-medium text-slate-900">{num(value)}</dd></div>
            ))}
          </dl>
        </div>
        <div className={`${card} xl:col-span-2`}>
          <SectionHeader title="Recent activity">
            <button type="button" onClick={() => goTo('audit')} className="text-xs font-semibold text-emerald-700 hover:underline">Open audit log →</button>
          </SectionHeader>
          <ul className="px-5 pb-4 divide-y divide-slate-100 text-sm">
            {activity.length === 0 && <li className="py-3 text-slate-500">No activity recorded yet.</li>}
            {activity.map(e => (
              <li key={e.id} className="py-2.5 flex items-center gap-3">
                <Chip tone={eventTone(e.event)}>{e.label}</Chip>
                <span className="flex-1 min-w-0 truncate text-slate-700">
                  {e.email || 'Unknown account'}{e.location ? ` · ${e.location}` : ''}{e.details?.target_email ? ` → ${e.details.target_email}` : ''}
                </span>
                <span className="text-xs text-slate-400 whitespace-nowrap">{ago(e.ts)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
