// Deterministic ATS checks and job-description matching. Missing keywords are
// suggestions only: nothing is added to the resume unless the person types it.
import { useMemo } from 'react';
import { CheckCircle2, CircleAlert, Info } from 'lucide-react';
import type { ResumeData } from '../types';
import { analyzeJobDescription, analyzeResumeAts } from '../atsAnalyzer';
import { TextArea } from './fields';

function Bar({ percent }: { percent: number }) {
  const tone = percent >= 70 ? 'bg-emerald-600' : percent >= 40 ? 'bg-amber-500' : 'bg-rose-500';
  return (
    <div className="h-1.5 w-full rounded-full bg-slate-200" role="presentation">
      <div className={`h-1.5 rounded-full ${tone}`} style={{ width: `${Math.max(2, percent)}%` }} />
    </div>
  );
}

function Terms({ words, tone }: { words: string[]; tone: 'match' | 'miss' }) {
  if (!words.length) return <p className="text-xs text-slate-400">None</p>;
  const style = tone === 'match' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-white text-slate-700 border-slate-300 border-dashed';
  return (
    <ul className="flex flex-wrap gap-1.5">
      {words.map(w => <li key={w} className={`rounded-md border px-2 py-0.5 text-xs ${style}`}>{w}</li>)}
    </ul>
  );
}

export default function AtsAudit({ data, jd, onJd, jdTitle }: { data: ResumeData; jd: string; onJd: (v: string) => void; jdTitle?: string | null }) {
  const report = useMemo(() => analyzeResumeAts(data), [data]);
  const match = useMemo(() => analyzeJobDescription(data, jd), [data, jd]);
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-900">Job description match</h3>
        <TextArea label={jdTitle ? `Job description (${jdTitle})` : 'Paste the job description'} rows={6} value={jd} onChange={onJd}
          maxLength={20000} placeholder="Paste the full posting: responsibilities and requirements." />
        {jd.trim() ? (
          match.extractedKeywords.length ? (
            <div className="rounded-xl border border-slate-200 p-4 space-y-3">
              <div className="flex items-baseline justify-between">
                <p className="text-sm text-slate-700"><b className="text-slate-900">{match.matchedKeywords.length}</b> of {match.extractedKeywords.length} terms from the posting appear in your resume</p>
                <p className="text-lg font-semibold text-slate-900">{match.matchPercent}%</p>
              </div>
              <Bar percent={match.matchPercent} />
              <div><p className="text-xs font-semibold text-slate-600 mb-1.5">In your resume</p><Terms words={match.matchedKeywords} tone="match" /></div>
              <div>
                <p className="text-xs font-semibold text-slate-600 mb-1.5">Not in your resume</p>
                <Terms words={match.missingKeywords} tone="miss" />
                <p className="mt-2 flex gap-1.5 text-xs text-slate-500"><Info size={14} className="shrink-0 mt-px" />
                  Add a term only where it is true for you, in your own words. Nothing is added automatically.</p>
              </div>
            </div>
          ) : <p className="text-sm text-slate-500">No recognisable skills or tools were found in this text.</p>
        ) : null}
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-900">Format checks</h3>
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
          {report.checks.map(c => (
            <li key={c.id} className="flex gap-3 p-3">
              {c.ok ? <CheckCircle2 size={18} className="shrink-0 text-emerald-600" aria-label="Passed" />
                : <CircleAlert size={18} className="shrink-0 text-amber-600" aria-label="Needs attention" />}
              <div><p className="text-sm font-medium text-slate-900">{c.label}</p><p className="text-xs text-slate-500">{c.detail}</p></div>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Keyword coverage by role family</h3>
          <p className="text-xs text-slate-500">{report.matched}/{report.total} common terms</p>
        </div>
        {report.groups.map(g => (
          <details key={g.group} className="rounded-xl border border-slate-200 p-3 group">
            <summary className="cursor-pointer list-none">
              <div className="flex items-baseline justify-between text-sm"><span className="font-medium text-slate-900">{g.group}</span><span className="text-slate-600">{g.percent}%</span></div>
              <div className="mt-2"><Bar percent={g.percent} /></div>
            </summary>
            <div className="mt-3 space-y-2">
              <Terms words={g.matched} tone="match" />
              <p className="text-xs font-semibold text-slate-600">Common in this field, not in your resume</p>
              <Terms words={g.missing} tone="miss" />
            </div>
          </details>
        ))}
        <p className="text-xs text-slate-500">A general guide for the field, not a requirement. Match the posting you are applying to first.</p>
      </section>
    </div>
  );
}
