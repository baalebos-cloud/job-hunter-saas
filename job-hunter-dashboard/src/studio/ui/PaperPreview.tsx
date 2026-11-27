// On-screen paper that follows the PDF engine's layout: same section order, titles,
// separators and text. The downloaded PDF (Full Preview) is the source of truth for page breaks.
import type { ReactNode } from 'react';
import type { Paper, ResumeData } from '../types';
import { PAPER_SIZES } from '../types';
import { SECTION_TITLES } from '../atsAnalyzer';

const clean = (s: string | undefined) => String(s ?? '').replace(/\s+/g, ' ').trim();
const join = (parts: Array<string | undefined>, sep: string) => parts.map(clean).filter(Boolean).join(sep);

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-[1.1em] break-inside-avoid-page">
      <h2 className="text-[1.12em] font-bold tracking-wide text-[#1f4e79] border-b-[1.5px] border-[#1f4e79] pb-[2px] mb-[0.45em]">{title}</h2>
      {children}
    </section>
  );
}

function Bullet({ children }: { children: ReactNode }) {
  return <li className="flex gap-[0.55em] pl-[0.35em]"><span aria-hidden="true">{'\u2022'}</span><span className="min-w-0">{children}</span></li>;
}

function LeftRight({ left, right }: { left: ReactNode; right: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <p className="min-w-0">{left}</p>
      {right && <p className="shrink-0 whitespace-nowrap">{right}</p>}
    </div>
  );
}

export default function PaperPreview({ data, paper }: { data: ResumeData; paper: Paper }) {
  const [w, h] = PAPER_SIZES[paper];
  const [SUMMARY, CORE, SOFT, PROJECTS, TECH, EXPERIENCE, EDUCATION, CERTS] = SECTION_TITLES;
  const contact1 = join([data.location, data.phone, data.email], ' | ');
  const contact2 = join([data.linkedin, data.github, data.portfolio], ' | ');
  const core = data.coreCompetencies.map(clean).filter(Boolean);
  const soft = data.softSkills.map(clean).filter(Boolean);
  const projects = data.projects.filter(p => clean(p.title));
  const groups = data.technicalSkills.filter(g => g.items.map(clean).filter(Boolean).length);
  const roles = data.experience.filter(r => clean(r.role) || clean(r.company));
  const schools = data.education.filter(e => clean(e.degree) || clean(e.institution));
  const certs = data.certifications.filter(c => clean(c.name));
  const empty = !clean(data.fullName) && !clean(data.summary) && !roles.length;

  return (
    // 1pt in the PDF = 1 unit here; the font size scales with the container width (cqw).
    <div className="studio-paper-wrap w-full [container-type:inline-size]">
      <article aria-label="Resume preview" className="studio-paper mx-auto bg-white text-[#121212] shadow-[0_1px_3px_rgba(15,23,42,.12),0_12px_32px_-12px_rgba(15,23,42,.25)]"
        style={{ aspectRatio: `${w} / ${h}`, minHeight: 'auto', padding: `${(46 / w) * 100}cqw ${(50 / w) * 100}cqw`,
          fontFamily: 'Helvetica, Arial, sans-serif', fontSize: `${(9.8 / w) * 100}cqw`, lineHeight: 1.32 }}>
        {empty ? (
          <p className="text-center text-slate-400 pt-[30%]">Your resume appears here as you type.</p>
        ) : (
          <>
            <header className="text-center">
              <h1 className="text-[1.84em] font-bold text-[#1f4e79] leading-tight">{clean(data.fullName).toUpperCase() || 'YOUR NAME'}</h1>
              {clean(data.headline) && <p className="mt-[1px] text-[1.06em] font-bold">{clean(data.headline)}</p>}
              {contact1 && <p className="mt-[1px] text-[0.95em] text-[#333]">{contact1}</p>}
              {contact2 && <p className="text-[0.95em] text-[#333] break-words">{contact2}</p>}
            </header>
            {clean(data.summary) && <Section title={SUMMARY}><p className="text-justify">{clean(data.summary)}</p></Section>}
            {core.length > 0 && <Section title={CORE}><p>{core.join(' | ')}</p></Section>}
            {soft.length > 0 && <Section title={SOFT}><p>{soft.join(' | ')}</p></Section>}
            {projects.length > 0 && (
              <Section title={PROJECTS}>
                {clean(data.projectsIntro) && <p className="italic mb-[0.2em]">{clean(data.projectsIntro)}</p>}
                <ul className="space-y-[0.15em]">
                  {projects.map((p, i) => (
                    <Bullet key={i}><b>{clean(p.title)}</b>{clean(p.tech) && ` (${clean(p.tech)})`}{clean(p.description) && `. ${clean(p.description)}`}</Bullet>
                  ))}
                </ul>
              </Section>
            )}
            {groups.length > 0 && (
              <Section title={TECH}>
                {groups.map((g, i) => <p key={i}><b>{clean(g.label)}: </b>{g.items.map(clean).filter(Boolean).join(', ')}</p>)}
              </Section>
            )}
            {roles.length > 0 && (
              <Section title={EXPERIENCE}>
                <div className="space-y-[0.4em]">
                  {roles.map((r, i) => {
                    const where = join([r.company, r.location], ' · ');
                    return (
                      <div key={i} className="break-inside-avoid-page">
                        <LeftRight left={<><b>{clean(r.role)}</b>{where && ` | ${where}`}</>} right={clean(r.dates)} />
                        <ul>
                          {r.bullets.map(clean).filter(Boolean).map((b, n) => <Bullet key={n}>{b}</Bullet>)}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}
            {schools.length > 0 && (
              <Section title={EDUCATION}>
                {schools.map((e, i) => <LeftRight key={i} left={<><b>{clean(e.degree)}</b>{clean(e.institution) && ` | ${clean(e.institution)}`}</>} right={clean(e.date)} />)}
              </Section>
            )}
            {certs.length > 0 && (
              <Section title={CERTS}>
                {certs.map((c, i) => <LeftRight key={i} left={<>{'•  '}<b>{clean(c.name)}</b>{clean(c.issuer) && `, ${clean(c.issuer)}`}</>} right={clean(c.date)} />)}
              </Section>
            )}
          </>
        )}
      </article>
    </div>
  );
}
