/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useEffect, useState } from 'react';
import { Briefcase, Building2, Check, Copy, ExternalLink, Globe, Sparkles } from 'lucide-react';
import { adminGet, message, num } from '../adminApi';
import { Banner, SectionHeader, Spinner, Stat, card } from '../ui';

function CopyButton({ text, label = 'Copy' }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); } catch { setDone(false); }
  };
  return (
    <button type="button" onClick={copy}
      className="inline-flex items-center gap-1.5 text-xs font-semibold rounded-lg px-2.5 py-1.5 border border-slate-200 bg-white text-slate-700 hover:bg-slate-50">
      {done ? <><Check size={13} />Copied</> : <><Copy size={13} />{label}</>}</button>
  );
}

function JobList({ title, subtitle, jobs, showPay }) {
  return (
    <section className={card}>
      <SectionHeader title={title} subtitle={subtitle} />
      <ul className="divide-y divide-slate-100 border-t border-slate-100">
        {jobs.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">Nothing to show yet.</li>}
        {jobs.map(j => (
          <li key={j.id} className="px-5 py-3 flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-900 truncate">{j.title}</div>
              <div className="text-xs text-slate-500 truncate">{j.company}{j.location ? ` · ${j.location}` : ''}{showPay && j.salary ? ` · ${j.salary}` : ''}</div>
            </div>
            <CopyButton text={j.link} label="Link" />
            <a href={j.link} target="_blank" rel="noreferrer" aria-label={`Open ${j.title}`} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100"><ExternalLink size={15} /></a>
          </li>))}
      </ul>
    </section>
  );
}

// Content for social media (content:read): built only from live jobs, ready to copy.
export default function ContentTab() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    adminGet('/console/content').then(setData).catch(err => setError(message(err, 'Content could not be loaded.')));
  }, []);
  if (error) return <Banner>{error}</Banner>;
  if (!data) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <Stat label="Live jobs" value={num(data.live_jobs)} icon={Briefcase} />
        <Stat label="New this week" value={num(data.new_this_week)} hint={`${num(data.remote_new_this_week)} remote`} icon={Sparkles} />
        <Stat label="Hiring companies" value={num(data.top_companies.length)} hint="With live roles (top 10 shown)" icon={Building2} />
      </div>

      <section className={card}>
        <SectionHeader title="Ready-to-copy posts" subtitle={data.note} />
        <div className="px-5 pb-5 grid grid-cols-1 lg:grid-cols-3 gap-3">
          {data.posts.length === 0 && <p className="text-sm text-slate-500">No live jobs yet, so there is nothing to post about.</p>}
          {data.posts.map(post => (
            <article key={post.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-col">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-900">{post.title}</h3>
                <CopyButton text={post.text} />
              </div>
              <p className="mt-2 text-sm text-slate-700 whitespace-pre-line break-words flex-1">{post.text}</p>
            </article>))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className={card}>
          <SectionHeader title="Top hiring companies" subtitle="By live roles" />
          <ol className="px-5 pb-5 text-sm divide-y divide-slate-100">
            {data.top_companies.map((c, i) => (
              <li key={c.company} className="py-2 flex justify-between"><span><span className="text-slate-400 mr-2">{i + 1}.</span>{c.company}</span><span className="text-slate-600">{num(c.open_roles)} role{c.open_roles > 1 ? 's' : ''}</span></li>))}
          </ol>
        </section>
        <JobList title="Newest remote roles" subtitle="Links carry campaign tags" jobs={data.newest_remote} />
        <JobList title="Highest-paid roles" subtitle="Yearly pay as listed by the employer" jobs={data.top_paid} showPay />
      </div>
      <p className="text-xs text-slate-500 inline-flex items-center gap-1"><Globe size={12} />Every post and link points to a real, live job on Baalebos.</p>
    </div>
  );
}
