// Deterministic ATS checks and job-description matching. Missing keywords are
// suggestions only: nothing is added to the resume unless the person types it.
import { useMemo } from 'react';
import type { ReactNode } from 'react';
import type { ResumeData } from '../types';
import { analyzeJobDescription, analyzeResumeAts } from '../atsAnalyzer';
import { TextArea } from './fields';

const mono = 'font-[JetBrains_Mono,ui-monospace,monospace] tabular-nums';

function Heading({ children, count }: { children: ReactNode; count?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-200 pb-1.5">
      <h3 className="text-[13px] font-bold uppercase tracking-wide text-[#1F4E79]">{children}</h3>
      {count && <span className={`${mono} text-xs text-slate-500`}>{count}</span>}
    </div>
  );
}

/** Terms as plain inline text separated by middle dots (no chips). */
function Terms({ label, words, muted }: { label: string; words: string[]; muted?: boolean }) {
  return (
    <p className={`text-[13px] leading-relaxed ${muted ? 'text-slate-500' : 'text-slate-800'}`}>
      <span className="font-semibold text-slate-700">{label}: </span>
      {words.length ? words.join(' · ') : <span className="text-slate-400">none</span>}
    </p>
  );
}

export default function AtsAudit({ data, jd, onJd, jdTitle }: { data: ResumeData; jd: string; onJd: (v: string) => void; jdTitle?: string | null }) {
  const report = useMemo(() => analyzeResumeAts(data), [data]);
  const match = useMemo(() => analyzeJobDescription(data, jd), [data, jd]);
  return (
    <div className="space-y-7">
      <section className="space-y-3" aria-label="Keyword coverage">
        <Heading count={`${report.matched}/${report.total}`}>Keyword coverage</Heading>
        {report.groups.map(g => (
          <div key={g.group} className="space-y-1">
            <p className="flex items-baseline justify-between text-[13px]">
              <span className="font-semibold text-slate-900">{g.group}</span>
              <span className={`${mono} text-slate-600`}>{g.matched.length}/{g.matched.length + g.missing.length}</span>
            </p>
            <Terms label="Matched" words={g.matched} />
            <Terms label="Missing" words={g.missing} muted />
          </div>
        ))}
        <p className="text-xs text-slate-500">A general guide for each field, not a requirement. Match the posting you are applying to first.</p>
      </section>

      <section className="space-y-2" aria-label="Structural readiness">
        <Heading count={`${report.checks.filter(c => c.ok).length}/${report.checks.length}`}>Structural readiness</Heading>
        <ul className="divide-y divide-slate-100">
          {report.checks.map(c => (
            <li key={c.id} className="py-2">
              <p className="text-[13px]">
                <span className={`font-semibold ${c.ok ? 'text-[#1F4E79]' : 'text-amber-700'}`}>{c.ok ? 'Pass' : 'Needs review'}</span>
                <span className="text-slate-400"> · </span><span className="font-medium text-slate-900">{c.label}</span>
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{c.detail}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3" aria-label="Job description matcher">
        <Heading count={jd.trim() && match.extractedKeywords.length ? `${match.matchedKeywords.length}/${match.extractedKeywords.length} · ${match.matchPercent}%` : undefined}>
          Job description match
        </Heading>
        <TextArea label={jdTitle ? `Job description (${jdTitle})` : 'Paste the job description'} rows={6} value={jd} onChange={onJd}
          maxLength={20000} placeholder="Paste the full posting: responsibilities and requirements." />
        {jd.trim() ? (
          match.extractedKeywords.length ? (
            <div className="space-y-1.5">
              <Terms label={`Matched (${match.matchedKeywords.length})`} words={match.matchedKeywords} />
              <Terms label={`Missing from resume (${match.missingKeywords.length})`} words={match.missingKeywords} muted />
              <p className="text-xs text-slate-500 pt-1">Add a term only where it is true for you, in your own words. Nothing is added automatically.</p>
            </div>
          ) : <p className="text-[13px] text-slate-500">No recognisable skills or tools were found in this text.</p>
        ) : null}
      </section>
    </div>
  );
}
