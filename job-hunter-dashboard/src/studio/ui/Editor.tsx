// The five editor tabs. Every field maps 1:1 to the PDF; nothing is generated.
import type { ResumeData } from '../types';
import { BulletLines, CommaField, Field, LineList, Repeater, TextArea } from './fields';
import AtsAudit from './AtsAudit';

export type EditorTab = 'profile' | 'skills' | 'experience' | 'education' | 'ats';
export const EDITOR_TABS: Array<[EditorTab, string]> = [
  ['profile', 'Profile & Summary'], ['skills', 'Skills & Keywords'], ['experience', 'Projects & Experience'],
  ['education', 'Education & Certs'], ['ats', 'ATS Audit'],
];

type Set = <K extends keyof ResumeData>(key: K, value: ResumeData[K]) => void;

export default function Editor({ tab, data, set, jd, onJd, jdTitle }: {
  tab: EditorTab; data: ResumeData; set: Set; jd: string; onJd: (v: string) => void; jdTitle?: string | null;
}) {
  if (tab === 'profile') return (
    <div className="space-y-4">
      <Field label="Full Name" value={data.fullName} onChange={v => set('fullName', v)} maxLength={120} />
      <Field label="Target Role Headline" value={data.headline} onChange={v => set('headline', v)} maxLength={300}
        placeholder="Cloud DevOps Engineer | AWS · Kubernetes · Terraform"
        hint="The role you are applying for first. Use the job's exact title when it is true for you." />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Location" value={data.location} onChange={v => set('location', v)} placeholder="Lagos, Nigeria" maxLength={160} />
        <Field label="Phone Number (optional)" type="tel" value={data.phone} onChange={v => set('phone', v)} maxLength={60} />
        <Field label="Email" type="email" value={data.email} onChange={v => set('email', v)} maxLength={254} />
        <Field label="LinkedIn URL" value={data.linkedin} onChange={v => set('linkedin', v)} placeholder="linkedin.com/in/…" maxLength={300} />
        <Field label="GitHub URL" value={data.github} onChange={v => set('github', v)} placeholder="github.com/…" maxLength={300} />
        <Field label="Portfolio / Website URL" value={data.portfolio} onChange={v => set('portfolio', v)} maxLength={300} />
      </div>
      <TextArea label="Career Summary" rows={6} value={data.summary} onChange={v => set('summary', v)} maxLength={3000}
        hint="Three or four sentences: what you do, the tools you use most, and one result you can prove." />
    </div>
  );

  if (tab === 'skills') return (
    <div className="space-y-5">
      <LineList label="Core Competencies" items={data.coreCompetencies} onChange={v => set('coreCompetencies', v)} max={40}
        placeholder={'CI/CD\nInfrastructure as Code\nIncident management'} hint="One area of practice per line." />
      <LineList label="Soft Skills" items={data.softSkills} onChange={v => set('softSkills', v)} max={20}
        placeholder={'Stakeholder communication\nMentoring'} hint="One per line." />
      <Repeater title="Technical Skills" addLabel="Add category" max={12} items={data.technicalSkills}
        onChange={v => set('technicalSkills', v)} make={() => ({ label: '', items: [] })} summary={g => g.label}
        render={(g, update) => (
          <div className="space-y-3">
            <Field label="Category Label" value={g.label} onChange={label => update({ label })} placeholder="Cloud, Languages, Monitoring…" maxLength={80} />
            <CommaField label="Comma-separated skills" items={g.items} onChange={items => update({ items })} max={40} placeholder="AWS, Terraform, Kubernetes" />
          </div>
        )} />
    </div>
  );

  if (tab === 'experience') return (
    <div className="space-y-6">
      <Field label="Projects section intro (optional)" value={data.projectsIntro} onChange={v => set('projectsIntro', v)} maxLength={600}
        placeholder="Selected personal and open-source projects." />
      <Repeater title="Projects" addLabel="Add project" max={12} items={data.projects}
        onChange={v => set('projects', v)} make={() => ({ title: '', tech: '', description: '' })} summary={p => p.title}
        render={(p, update) => (
          <div className="space-y-3">
            <Field label="Title" value={p.title} onChange={title => update({ title })} maxLength={160} />
            <Field label="Tech Stack" value={p.tech} onChange={tech => update({ tech })} placeholder="Terraform, GitHub Actions, EKS" maxLength={300} />
            <TextArea label="Description" rows={3} value={p.description} onChange={description => update({ description })} maxLength={1500}
              hint="What you built and the result." />
          </div>
        )} />
      <Repeater title="Professional Experience" addLabel="Add role" max={20} items={data.experience}
        onChange={v => set('experience', v)} make={() => ({ role: '', company: '', location: '', dates: '', bullets: [] })}
        summary={r => [r.role, r.company].filter(Boolean).join(' · ')}
        render={(r, update) => (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Role" value={r.role} onChange={role => update({ role })} maxLength={160} />
              <Field label="Company" value={r.company} onChange={company => update({ company })} maxLength={160} />
              <Field label="Location" value={r.location} onChange={location => update({ location })} maxLength={160} />
              <Field label="Dates" value={r.dates} onChange={dates => update({ dates })} placeholder="Jan 2022 – Present" maxLength={80} />
            </div>
            <BulletLines label="Bullet points (one per line)" bullets={r.bullets} onChange={bullets => update({ bullets })} max={15} />
          </div>
        )} />
    </div>
  );

  if (tab === 'education') return (
    <div className="space-y-6">
      <Repeater title="Education" addLabel="Add education" max={10} items={data.education}
        onChange={v => set('education', v)} make={() => ({ degree: '', institution: '', date: '' })}
        summary={e => [e.degree, e.institution].filter(Boolean).join(' · ')}
        render={(e, update) => (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Degree" value={e.degree} onChange={degree => update({ degree })} maxLength={200} />
            <Field label="Institution" value={e.institution} onChange={institution => update({ institution })} maxLength={200} />
            <Field label="Date" value={e.date} onChange={date => update({ date })} placeholder="2018" maxLength={80} />
          </div>
        )} />
      <Repeater title="Professional Certifications" addLabel="Add certification" max={20} items={data.certifications}
        onChange={v => set('certifications', v)} make={() => ({ name: '', issuer: '', date: '' })} summary={c => c.name}
        render={(c, update) => (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Name" value={c.name} onChange={name => update({ name })} maxLength={200} />
            <Field label="Issuer" value={c.issuer} onChange={issuer => update({ issuer })} maxLength={160} />
            <Field label="Date" value={c.date} onChange={date => update({ date })} placeholder="2024" maxLength={80} />
          </div>
        )} />
    </div>
  );

  return <AtsAudit data={data} jd={jd} onJd={onJd} jdTitle={jdTitle} />;
}
