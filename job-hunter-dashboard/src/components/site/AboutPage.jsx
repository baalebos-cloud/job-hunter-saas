import PublicPage from './PublicPage';
import SEO from '../SEO';

const PRINCIPLES = [
  ['Nothing invented', 'Every line of a tailored resume comes from the resume you uploaded. We reword; we never add skills, employers, dates or results you have not written.'],
  ['People decide', 'Match scores help you choose where to apply. Employers on Baalebos see every answer and make their own decisions; nobody is rejected automatically.'],
  ['Your data is yours', 'No advertising, no selling data. Export or delete everything from Settings whenever you want.'],
];

// /about
export default function AboutPage() {
  return (
    <PublicPage>
      <SEO path="/about" title="About" description="Why Baalebos exists and how it works." />
      <section className="max-w-3xl mx-auto px-5 sm:px-8 py-16">
        <p className="text-sm font-bold uppercase tracking-widest text-emerald-700">About</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight">Good engineers should not be filtered out by software.</h1>
        <p className="mt-6 text-lg text-slate-700 leading-8">Baalebos tailors your resume to each job you apply for, using only your real experience, and shows you how well you match before you apply. Employers who post on Baalebos ask the questions their role needs and review tailored resumes with answers side by side.</p>
        <p className="mt-4 text-lg text-slate-700 leading-8">It was founded by Oluwadare Jayeola, a cloud and DevOps engineer, to help tech talent everywhere get past applicant tracking systems honestly.</p>
        <div className="mt-12 grid sm:grid-cols-3 gap-4">
          {PRINCIPLES.map(([title, text]) => (
            <div key={title} className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="font-semibold text-slate-900">{title}</h2>
              <p className="mt-2 text-sm text-slate-600 leading-6">{text}</p>
            </div>))}
        </div>
        <div className="mt-12 flex flex-wrap gap-3">
          <a href="/signup" className="rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-semibold px-5 py-3">Start free</a>
          <a href="/contact" className="rounded-xl border border-slate-300 bg-white hover:bg-slate-50 font-semibold px-5 py-3">Contact us</a>
        </div>
      </section>
    </PublicPage>
  );
}
