/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useCallback, useEffect, useState } from 'react';
import { Download, Link2, Mail, MousePointerClick, TrendingUp, Wallet } from 'lucide-react';
import { adminGet, downloadCsv, message, num } from '../adminApi';
import { Banner, Button, SectionHeader, Segmented, Spinner, Stat, card } from '../ui';
import { Bars } from './AnalyticsTab';

const PARTNER_NAMES = { micro1: 'micro1', mercor: 'Mercor' };
const since = (iso) => (iso ? `since ${new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}` : 'tracking starts with the next event');

function Funnel({ steps }) {
  const top = steps[0]?.count || 0;
  return (
    <ol className="px-5 pb-5 space-y-2.5">
      {steps.map(s => (
        <li key={s.step}>
          <div className="flex justify-between text-sm"><span className="text-slate-700">{s.step}</span>
            <span className="font-semibold text-slate-900">{num(s.count)}{s.pct != null && <span className="ml-2 text-xs font-normal text-slate-500">{s.pct}%</span>}</span></div>
          <div className="mt-1 h-2.5 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${top ? (100 * s.count) / top : 0}%` }} />
          </div>
        </li>))}
    </ol>
  );
}

function Campaigns({ days }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    adminGet('/console/campaigns', { days }).then(setData).catch(err => setError(message(err, 'Campaign results could not be loaded.')));
  }, [days]);
  if (error) return <Banner>{error}</Banner>;
  if (!data) return <Spinner />;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <section className={`${card} xl:col-span-2 overflow-hidden`}>
        <SectionHeader title="Sign-ups by campaign" subtitle={`First link that brought each person, last ${data.days} days · ${num(data.total_signups)} sign-ups`} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500 border-y border-slate-100">
              <th className="px-5 py-2 font-medium">Source</th><th className="px-3 py-2 font-medium">Medium</th><th className="px-3 py-2 font-medium">Campaign</th>
              <th className="px-3 py-2 font-medium text-right">Sign-ups</th><th className="px-3 py-2 font-medium text-right">Verified</th><th className="px-5 py-2 font-medium text-right">Paid</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {data.sources.length === 0 && <tr><td colSpan={6} className="px-5 py-6 text-center text-slate-500">No sign-ups in this period yet.</td></tr>}
              {data.sources.map(r => (
                <tr key={`${r.source}|${r.medium}|${r.campaign}`}>
                  <td className="px-5 py-2 font-medium text-slate-900">{r.source}</td><td className="px-3 py-2 text-slate-600">{r.medium || '—'}</td>
                  <td className="px-3 py-2 text-slate-600">{r.campaign || '—'}</td><td className="px-3 py-2 text-right">{num(r.signups)}</td>
                  <td className="px-3 py-2 text-right">{num(r.verified)}</td><td className="px-5 py-2 text-right">{num(r.paid)}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
        <div className="px-5 py-3 border-t border-slate-100 text-xs text-slate-500 flex gap-2 items-start">
          <Link2 size={14} className="shrink-0 mt-0.5" />
          <span>Tag every link you share so it shows up here, for example <code className="break-all text-slate-700">{data.how_to_tag}</code></span>
        </div>
      </section>
      <div className="space-y-4">
        <section className={card}>
          <SectionHeader title="Partner card clicks" subtitle={data.clicks_tracked_since ? since(data.clicks_tracked_since) : 'Counted from the first click'} />
          <ul className="px-5 pb-5 space-y-4">
            {data.partners.map(p => (
              <li key={p.partner}>
                <div className="flex justify-between text-sm"><span className="font-medium text-slate-900">{PARTNER_NAMES[p.partner] || p.partner}</span>
                  <span className="text-slate-600"><MousePointerClick size={13} className="inline mr-1" />{num(p.clicks_7d)} this week · {num(p.clicks_30d)} in 30 days</span></div>
                <div className="mt-2"><Bars series={p.daily} color="bg-violet-500" label={`${p.partner} clicks`} /></div>
              </li>))}
          </ul>
        </section>
        <section className={card}>
          <SectionHeader title="Top referring sites" />
          <ul className="px-5 pb-5 text-sm divide-y divide-slate-100">
            {data.referrers.length === 0 && <li className="py-2 text-slate-500">None yet.</li>}
            {data.referrers.map(r => <li key={r.referrer} className="py-2 flex justify-between"><span>{r.referrer}</span><span className="text-slate-600">{num(r.signups)} sign-ups · {num(r.paid)} paid</span></li>)}
          </ul>
        </section>
      </div>
    </div>
  );
}

// Go-to-market (growth:read) and campaign results (campaigns:read).
export default function GrowthTab({ permissions, onError }) {
  const full = permissions.includes('growth:read');
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    if (!full) return;
    try { setData(await adminGet('/console/growth', { days })); setError(''); }
    catch (err) { if (!onError?.(err)) setError(message(err, 'Growth figures could not be loaded.')); }
  }, [days, full, onError]);
  useEffect(() => { load(); }, [load]);

  const periods = <Segmented value={days} onChange={setDays} options={[[30, '30 days'], [90, '90 days'], [365, '12 months']]} />;
  if (!full) return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold text-slate-900">Campaign results</h2>{periods}</div>
      <Campaigns days={days} />
    </div>
  );
  if (error) return <Banner>{error}</Banner>;
  if (!data) return <Spinner />;
  const p = data.plans;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-900">Go-to-market</h2>
        <div className="flex items-center gap-2">{periods}
          <Button icon={Download} onClick={() => downloadCsv('/console/growth.csv', { days }, `baalebos-growth-${days}d.csv`)}>CSV</Button></div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Estimated monthly revenue" value={`$${num(p.estimated_mrr)}`} hint="At list price · Stripe is the source of truth" icon={Wallet} />
        <Stat label="Paid accounts" value={num(p.pro + p.enterprise)} hint={`${num(p.pro)} Pro · ${num(p.enterprise)} Enterprise · ${num(p.free)} Free`} icon={TrendingUp} />
        <Stat label="Upgrades" value={num(p.upgrades)} hint={`${num(p.cancellations)} cancelled · ${num(p.payment_failures)} failed payments · ${since(p.changes_tracked_since)}`} icon={TrendingUp} />
        <Stat label="Job alert emails" value={num(data.alerts.sent_30d)} hint={`${num(data.alerts.sent_7d)} this week · ${num(data.alerts.subscribers)} subscribers · ${num(data.alerts.unsubscribed)} unsubscribed`} icon={Mail} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className={card}>
          <SectionHeader title="Funnel" subtitle={`People who signed up in the last ${data.days} days`} />
          <Funnel steps={data.funnel} />
        </section>
        <section className={`${card} lg:col-span-2`}>
          <SectionHeader title="Weekly sign-ups and tailored resumes" subtitle="Last 12 weeks" />
          <div className="px-5 pb-5 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Bars series={data.weekly.map(w => ({ date: w.week, count: w.signups }))} label="Weekly sign-ups" />
            <Bars series={data.weekly.map(w => ({ date: w.week, count: w.resumes }))} color="bg-violet-500" label="Weekly tailored resumes" />
          </div>
          <div className="px-5 pb-5 grid grid-cols-3 gap-3 text-sm">
            {[['Referral invites', data.referrals.invites], ['Signed up from referrals', data.referrals.signed_up], ['Referrals that paid', data.referrals.converted]].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="text-xl font-semibold text-slate-900">{num(value)}</div></div>))}
          </div>
        </section>
      </div>
      <p className="text-xs text-slate-500">{p.mrr_note}</p>
      <Campaigns days={days} />
    </div>
  );
}
