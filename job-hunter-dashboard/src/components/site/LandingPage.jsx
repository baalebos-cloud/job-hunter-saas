/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import SEO from '../SEO';
import SiteFooter from './SiteFooter';

// The public landing page. Every claim here matches what the product does today;
// the hero resume uses only details from the founder's own resume.
const display = { fontFamily: "'Inter Tight', Inter, sans-serif" };
const navy = '#1F4E79';

function Check({ dark }) {
  return <span className={`mt-0.5 grid h-[22px] w-[22px] shrink-0 place-items-center rounded-md text-[13px] font-bold ${dark ? 'bg-emerald-500/15 text-emerald-300' : 'bg-emerald-50 text-emerald-700'}`}>✓</span>;
}

function Mark({ children }) {
  return <mark className="rounded-sm bg-emerald-100 px-0.5 text-emerald-950">{children}</mark>;
}

// A tailored resume (the founder's real details) with what Baalebos shows around it.
function HeroScene() {
  return (
    <div className="relative mx-auto w-full max-w-[600px] lg:h-[540px]" aria-label="Example: a resume tailored for a Cloud Engineer job">
      <div className="absolute left-6 top-2 z-20 hidden rounded-lg bg-slate-900 px-3 py-2 text-[12.5px] font-semibold text-white shadow-lg sm:block">Headline set to the job&apos;s role</div>
      <div className="relative z-10 rounded-md border border-slate-200 bg-white p-7 shadow-[0_30px_60px_-30px_rgba(11,19,36,.35)] lg:absolute lg:left-0 lg:top-14 lg:w-[322px]"
        style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontSize: 10.5, lineHeight: 1.45, color: '#111' }}>
        <div className="text-center text-[17px] font-bold tracking-wide" style={{ color: navy }}>OLUWADARE JAYEOLA</div>
        <div className="mt-0.5 text-center font-bold"><Mark>Cloud Engineer</Mark> | AWS · GCP · Terraform · Kubernetes</div>
        <div className="text-center text-[9.5px] text-slate-600">Lagos, Nigeria | github.com/baalebos-cloud</div>
        {[['CAREER SUMMARY', <p key="s">Cloud DevOps engineer automating infrastructure across <Mark>AWS</Mark> and Google Cloud with <Mark>Terraform</Mark> and Ansible. Cut deployment failures by 30% and reduced manual operational toil by 80%.</p>],
          ['CORE COMPETENCIES', <p key="c">AWS (EC2, VPC, IAM, S3, Lambda) | <Mark>Kubernetes</Mark> | CI/CD (GitHub Actions, Jenkins) | Linux | Python, Bash</p>],
          ['CERTIFICATIONS', <p key="t"><b>AWS Certified Cloud Practitioner (CLF-C02)</b></p>]].map(([title, body]) => (
          <div key={title}>
            <div className="mt-3 pb-px text-[10.5px] font-bold tracking-wide" style={{ color: navy, borderBottom: `1.25px solid ${navy}` }}>{title}</div>
            <div className="mt-1">{body}</div>
          </div>))}
      </div>
      <div className="z-20 mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_24px_50px_-24px_rgba(11,19,36,.4)] lg:absolute lg:right-0 lg:top-0 lg:mt-0 lg:w-[196px]">
        <div className="flex items-center gap-3.5">
          <div className="grid h-[70px] w-[70px] place-items-center rounded-full" style={{ background: 'conic-gradient(#10b981 86%, #e5e7eb 0)' }}>
            <div className="grid h-14 w-14 place-items-center rounded-full bg-white text-lg font-extrabold" style={display}>86%</div>
          </div>
          <div><div className="text-[15px] font-bold">Job match</div><div className="text-xs text-slate-500">example · was 61% before</div></div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5 text-[11.5px] font-semibold">
          {['AWS', 'Terraform', 'Kubernetes', 'CI/CD'].map(k => <span key={k} className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-800">{k}</span>)}
          <span className="rounded-full bg-rose-50 px-2 py-0.5 text-rose-800">Helm</span>
        </div>
      </div>
      <div className="z-20 mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_24px_50px_-24px_rgba(11,19,36,.4)] lg:absolute lg:bottom-5 lg:right-0 lg:mt-0 lg:w-[300px]">
        <div className="text-[11.5px] font-bold uppercase tracking-wider text-rose-700">Refused by Baalebos</div>
        <s className="mt-1.5 block text-[13.5px] text-slate-400 decoration-rose-500">Led a team of 8 engineers running Kubernetes…</s>
        <p className="mt-1.5 text-[12.5px] text-slate-500">The resume never says that, so it was not written.</p>
      </div>
    </div>
  );
}

const STEPS = [
  ['Add your resume', 'Upload a PDF or Word file. Baalebos reads your experience, skills and education from it.', 'Read from your file: roles, dates, skills, education'],
  ['Pick a job', 'Choose one from the job board, or paste any description from LinkedIn, Indeed or a careers page.', 'Cloud Engineer · 14 requirements found'],
  ['Check, then apply', 'Review what changed, confirm skills you really have, download PDF or Word, and apply.', 'Match before and after · PDF and Word ready'],
];
const PLANS = [
  ['Free', '$0', '', 'For trying it on your next application.', ['3 resume scans a month', 'PDF and Word download', 'Job board and application tracker'], 'Start free', '/signup', false],
  ['Pro', '$19', ' / month', 'For an active job search.', ['Unlimited resume scans', 'Priority processing', 'History of your last 30 resumes'], 'Go Pro', '/pricing', true],
  ['Enterprise', '$49', ' / month', 'For bootcamps, agencies and teams.', ['Everything in Pro', 'Up to 10 team seats', 'Bulk tailoring, API and custom branding'], 'Choose Enterprise', '/pricing', false],
];
const FAQ = [
  ['Will it add skills I don\'t have?', 'No. Skills the job asks for that your resume does not show are listed as suggestions. They are added only if you confirm you have used them.'],
  ['Can applicant tracking systems read the PDF?', 'Yes. It is a single-column, text-based PDF: every word can be selected and copied.'],
  ['Who can see my resume?', 'Only you, and an employer you choose to apply to on Baalebos. You can export or delete everything from Settings.'],
  ['Do I need a card for the free plan?', 'No. The free plan gives you 3 resume scans every month.'],
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#fbfaf7] text-[#0b1324]" style={{ fontFamily: 'Inter, sans-serif' }}>
      <SEO path="/" description="Baalebos tailors your resume to every job you apply for, using only your real experience, and shows how well you match before you apply." />
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-[#fbfaf7]/90 backdrop-blur">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center gap-8 px-5 sm:px-8">
          <a href="/" className="text-[22px] font-extrabold tracking-tight" style={display}>baalebos<span className="text-emerald-500">.</span></a>
          <nav className="hidden flex-1 gap-7 text-[15px] text-slate-600 md:flex" aria-label="Main">
            <a href="#how" className="hover:text-slate-900">How it works</a><a href="#honest" className="hover:text-slate-900">Nothing invented</a>
            <a href="#employers" className="hover:text-slate-900">For employers</a><a href="#pricing" className="hover:text-slate-900">Pricing</a>
          </nav>
          <span className="flex-1 md:hidden" />
          <a href="/login" className="rounded-[10px] border border-slate-300 bg-white px-4 py-2.5 text-[15px] font-semibold">Sign in</a>
          <a href="/signup" className="hidden rounded-[10px] bg-slate-900 px-4 py-2.5 text-[15px] font-semibold text-white sm:inline-block">Start free</a>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-14 px-5 pb-10 pt-14 sm:px-8 lg:grid-cols-[1fr_1.02fr] lg:pt-20">
        <div>
          <p className="inline-flex items-center gap-2.5 rounded-full border border-slate-200 bg-white py-1.5 pl-1.5 pr-3.5 text-[12.5px] font-medium text-slate-700 sm:text-[13.5px]">
            <span className="whitespace-nowrap rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700">Honest AI</span>Every line checked against your own resume</p>
          <h1 className="mt-6 text-[44px] font-extrabold leading-[1.03] tracking-[-0.038em] sm:text-[60px] lg:text-[66px]" style={display}>
            Get past the screen. <span className="relative whitespace-nowrap"><span className="absolute inset-x-0 bottom-1.5 -z-0 h-2.5 rounded bg-emerald-200" aria-hidden="true" /><span className="relative">Get the interview.</span></span></h1>
          <p className="mt-6 max-w-[540px] text-[19px] leading-8 text-slate-700">Baalebos rewrites your resume for each job you apply to, using only your real experience, and shows you how well you match before you hit apply.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="/signup" className="rounded-[10px] bg-emerald-700 px-5 py-3 text-[15px] font-semibold text-white hover:bg-emerald-800">Tailor my resume, free →</a>
            <a href="#how" className="rounded-[10px] border border-slate-300 bg-white px-5 py-3 text-[15px] font-semibold hover:bg-slate-50">See how it works</a>
          </div>
          <ul className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
            {['Nothing invented', 'Text-based PDF that ATS can read', 'Free plan, no card'].map(t => <li key={t}><span className="mr-1.5 font-bold text-emerald-700">✓</span>{t}</li>)}
          </ul>
        </div>
        <HeroScene />
      </section>

      <section className="border-y border-slate-200 bg-white" aria-label="What you get">
        <div className="mx-auto grid max-w-6xl sm:grid-cols-2 lg:grid-cols-4">
          {[['Tailored per job', 'Rewritten around each job description'], ['Match before you apply', 'See what is covered and what is missing'],
            ['ATS-ready PDF', 'Real text, single column, A4 or Letter'], ['Live tech jobs', 'Job board with daily alerts']].map(([t, d], i) => (
            <div key={t} className={`px-6 py-6 ${i ? 'border-t sm:border-t-0 sm:border-l' : ''} border-slate-200`}>
              <div className="text-[17px] font-bold" style={display}>{t}</div><div className="text-sm text-slate-500">{d}</div></div>))}
        </div>
      </section>

      <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-24 sm:px-8">
        <p className="text-[13px] font-bold uppercase tracking-[0.12em] text-emerald-700">How it works</p>
        <h2 className="mt-3 max-w-3xl text-[34px] font-extrabold leading-[1.06] tracking-[-0.04em] sm:text-[46px]" style={display}>From one resume to the right resume for every job.</h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {STEPS.map(([title, text, mini], i) => (
            <div key={title} className="rounded-2xl border border-slate-200 bg-white p-6">
              <div className="grid h-[34px] w-[34px] place-items-center rounded-[9px] bg-slate-900 text-[15px] font-bold text-white" style={display}>{i + 1}</div>
              <h3 className="mt-5 text-xl font-bold tracking-tight" style={display}>{title}</h3>
              <p className="mt-1.5 text-[15px] text-slate-500">{text}</p>
              <p className="mt-5 whitespace-pre-line rounded-[10px] border border-dashed border-slate-300 bg-[#fcfcfb] p-3 text-[12.5px] text-slate-700">{mini}</p>
            </div>))}
        </div>
      </section>

      <section id="honest" className="mx-auto grid max-w-6xl scroll-mt-20 items-center gap-14 px-5 pb-24 sm:px-8 lg:grid-cols-2">
        <div>
          <p className="text-[13px] font-bold uppercase tracking-[0.12em] text-emerald-700">Honest by design</p>
          <h2 className="mt-3 text-[34px] font-extrabold leading-[1.06] tracking-[-0.04em] sm:text-[46px]" style={display}>It rewords your experience. It never invents it.</h2>
          <p className="mt-4 max-w-xl text-lg text-slate-700">Tools that add skills you do not have get people caught out in interviews. Every line Baalebos writes is checked against the resume you uploaded.</p>
          <ul className="mt-7 space-y-3 text-base">
            {['Uses the job\'s own words for skills you already list', 'Puts your most relevant achievements first', 'Never changes titles, employers, dates or numbers'].map(t => <li key={t} className="flex gap-3"><Check />{t}</li>)}
          </ul>
        </div>
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white text-[15px]">
          {[['Original', 'text-slate-500', 'Ran production workloads on K8s and Terraform across three AWS accounts.'],
            ['Tailored', 'text-emerald-700', <>Ran production workloads on <b>Kubernetes</b> and Terraform across three AWS accounts.</>],
            ['Refused', 'text-rose-700', <s key="r" className="text-slate-400 decoration-rose-500">Led a team of 8 running production workloads on Kubernetes.</s>]].map(([label, tone, text], i) => (
            <div key={label} className={`grid grid-cols-[96px_1fr] gap-3.5 px-5 py-4 ${i ? 'border-t border-slate-200' : ''}`}>
              <span className={`pt-0.5 text-[11.5px] font-bold uppercase tracking-[0.08em] ${tone}`}>{label}</span><span>{text}</span></div>))}
        </div>
      </section>

      <section id="employers" className="scroll-mt-20 bg-[#0b1324] text-slate-200">
        <div className="mx-auto grid max-w-6xl items-center gap-14 px-5 py-24 sm:px-8 lg:grid-cols-2">
          <div>
            <p className="text-[13px] font-bold uppercase tracking-[0.12em] text-emerald-400">For employers</p>
            <h2 className="mt-3 text-[34px] font-extrabold leading-[1.06] tracking-[-0.04em] text-white sm:text-[46px]" style={display}>Ask every applicant the questions your role needs.</h2>
            <p className="mt-4 max-w-xl text-lg text-slate-400">Post a job on Baalebos, set your own application form, and review tailored resumes with answers side by side.</p>
            <ul className="mt-7 space-y-3">
              {['Work authorisation, notice period, experience and up to 20 questions of your own', 'Filter applicants by their answers', 'No automatic rejections: people make the decision'].map(t => <li key={t} className="flex gap-3"><Check dark />{t}</li>)}
            </ul>
            <a href="/hr/signup" className="mt-8 inline-block rounded-[10px] bg-emerald-600 px-5 py-3 font-semibold text-white hover:bg-emerald-500">Post a job</a>
          </div>
          <div className="rounded-2xl border border-[#23304d] bg-[#111c33] p-5 text-[14.5px] text-slate-300">
            {[['Are you authorised to work in the United Kingdom?', 'Required'], ['Years of relevant experience', 'Required'],
              ['Have you run Kubernetes in production?', 'Your question'], ['Link to something you built', 'Optional']].map(([q, tag], i) => (
              <div key={q} className={`flex justify-between gap-3 py-3 ${i ? 'border-t border-[#23304d]' : ''}`}>
                <span>{q}</span><span className="h-fit whitespace-nowrap rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">{tag}</span></div>))}
          </div>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-24 sm:px-8">
        <p className="text-[13px] font-bold uppercase tracking-[0.12em] text-emerald-700">Pricing</p>
        <h2 className="mt-3 max-w-3xl text-[34px] font-extrabold leading-[1.06] tracking-[-0.04em] sm:text-[46px]" style={display}>Start free. Upgrade when you are applying every week.</h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {PLANS.map(([name, price, per, blurb, features, cta, href, featured]) => (
            <div key={name} className={`relative rounded-[18px] bg-white p-7 ${featured ? 'border-2 border-slate-900' : 'border border-slate-200'}`}>
              {featured && <span className="absolute -top-3 left-6 rounded-full bg-slate-900 px-3 py-0.5 text-xs font-semibold text-white">For an active search</span>}
              <h3 className="text-lg font-bold" style={display}>{name}</h3>
              <div className="mt-2 text-5xl font-extrabold tracking-[-0.04em]" style={display}>{price}<span className="text-[15px] font-medium tracking-normal text-slate-500">{per}</span></div>
              <p className="mt-1 text-slate-500">{blurb}</p>
              <ul className="my-6 space-y-2.5 text-[15px] text-slate-700">{features.map(f => <li key={f}><span className="mr-2 font-bold text-emerald-700">✓</span>{f}</li>)}</ul>
              <a href={href} className={`inline-block rounded-[10px] px-5 py-2.5 font-semibold ${featured ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white'}`}>{cta}</a>
            </div>))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-24 sm:px-8" aria-labelledby="faq-title">
        <p className="text-[13px] font-bold uppercase tracking-[0.12em] text-emerald-700">Questions</p>
        <h2 id="faq-title" className="mt-3 text-[34px] font-extrabold tracking-[-0.04em] sm:text-[46px]" style={display}>Before you start</h2>
        <dl className="mt-10 grid gap-x-12 md:grid-cols-2">
          {FAQ.map(([q, a]) => <div key={q} className="border-t border-slate-200 py-5"><dt className="text-[17px] font-bold" style={display}>{q}</dt><dd className="mt-1.5 text-[15px] text-slate-500">{a}</dd></div>)}
        </dl>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-24 sm:px-8">
        <div className="flex flex-col items-start justify-between gap-8 rounded-3xl bg-gradient-to-b from-emerald-900 to-emerald-800 p-9 text-white sm:p-16 md:flex-row md:items-center">
          <div><h2 className="text-[30px] font-extrabold leading-tight tracking-[-0.04em] sm:text-[42px]" style={display}>Your next application deserves a resume written for it.</h2>
            <p className="mt-3 text-[17px] text-emerald-200">Upload once. Tailor in minutes. Apply with confidence.</p></div>
          <a href="/signup" className="shrink-0 rounded-[10px] bg-white px-5 py-3 font-semibold text-emerald-900">Start free →</a>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
