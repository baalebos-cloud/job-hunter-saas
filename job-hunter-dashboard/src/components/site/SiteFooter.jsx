// The public site footer: product, employers, company and legal links.
const COLUMNS = [
  ['Product', [['Tailor a resume', '/optimizer'], ['Job board', '/jobs'], ['Pricing', '/pricing'], ['API for developers', '/developers']]],
  ['Employers', [['Post a job', '/hr/signup'], ['Employer sign in', '/hr/login']]],
  ['Company', [['About', '/about'], ['Contact', '/contact'], ['Help centre', '/help'], ['Referral programme', '/referral']]],
  ['Legal', [['Terms & Conditions', '/legal/terms'], ['Privacy Policy', '/legal/privacy'], ['Cookie Policy', '/legal/cookies'],
    ['Refund Policy', '/legal/refunds'], ['Acceptable Use', '/legal/acceptable-use']]],
];

export default function SiteFooter() {
  return (
    <footer className="bg-white border-t border-slate-200 text-slate-600" style={{ fontFamily: 'Inter, sans-serif' }}>
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-14 grid grid-cols-2 md:grid-cols-[1.6fr_repeat(4,1fr)] gap-8">
        <div className="col-span-2 md:col-span-1">
          <a href="/" className="text-xl font-extrabold tracking-tight text-slate-900">baalebos<span className="text-emerald-500">.</span></a>
          <p className="mt-3 text-sm max-w-xs">Tailored resumes and honest job matching for tech talent everywhere.</p>
        </div>
        {COLUMNS.map(([title, links]) => (
          <nav key={title} aria-label={title}>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">{title}</h2>
            <ul className="mt-3 space-y-2.5 text-sm">{links.map(([label, href]) => <li key={href}><a href={href} className="hover:text-slate-900">{label}</a></li>)}</ul>
          </nav>))}
      </div>
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-6 border-t border-slate-100 flex flex-wrap justify-between gap-3 text-xs">
        <span>© {new Date().getFullYear()} Baalebos. All rights reserved.</span>
        <span className="flex gap-4">
          <a href="mailto:support@baalebo.xyz" className="hover:text-slate-900">support@baalebo.xyz</a>
          <a href="https://www.linkedin.com/in/oluwadare-jayeola-6874591b4/" target="_blank" rel="noopener noreferrer" className="hover:text-slate-900">LinkedIn</a>
          <a href="https://github.com/baalebos-cloud" target="_blank" rel="noopener noreferrer" className="hover:text-slate-900">GitHub</a>
        </span>
      </div>
    </footer>
  );
}
