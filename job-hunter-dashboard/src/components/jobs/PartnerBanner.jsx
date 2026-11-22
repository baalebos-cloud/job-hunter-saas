import { useState } from 'react';
import { ArrowUpRight, Clock, Globe, Sparkles, Wallet, X } from 'lucide-react';

// Partner opportunities shown on the Jobs page. Listings live on the partner's
// site: we link out with our referral link and never copy their jobs.
export const PARTNERS = [{
  id: 'micro1',
  name: 'micro1',
  initials: 'm1',
  headline: 'AI training & expert roles at micro1',
  pitch: 'Work remotely on flexible projects that train frontier AI models for leading AI companies. '
    + 'Roles for engineers, data specialists and domain experts; no prior AI-training experience needed.',
  facts: [[Globe, 'Remote, worldwide'], [Wallet, 'Paid hourly'], [Clock, 'Flexible hours']],
  url: 'https://refer.micro1.ai/referral/jobs?referralCode=ff238650-b95b-4a56-b3ae-b0dafef81ed2'
    + '&utm_source=referral&utm_medium=share&utm_campaign=job_referral',
}];

const DISMISS_KEY = 'partner-banner-dismissed';

function dismissed() {
  try { return JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]'); } catch { return []; }
}

export default function PartnerBanner() {
  const [hidden, setHidden] = useState(dismissed);
  const visible = PARTNERS.filter(p => !hidden.includes(p.id));
  if (!visible.length) return null;

  const hide = (id) => {
    const next = [...hidden, id];
    setHidden(next);
    try { localStorage.setItem(DISMISS_KEY, JSON.stringify(next)); } catch { /* private mode: hide for this visit only */ }
  };

  return visible.map(p => (
    <aside key={p.id} aria-label={`Partner opportunity: ${p.name}`}
      className="mt-4 relative overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-r from-violet-50 via-white to-emerald-50 p-4 sm:p-5">
      <button type="button" onClick={() => hide(p.id)} aria-label={`Hide ${p.name}`}
        className="absolute top-3 right-3 p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-white/70"><X size={16} /></button>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 pr-6">
        <div className="w-12 h-12 shrink-0 rounded-xl bg-slate-900 text-white grid place-items-center font-bold tracking-tight">{p.initials}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-violet-700 bg-violet-100 rounded-full px-2 py-0.5">
              <Sparkles size={11} />Partner opportunity</span>
          </div>
          <h3 className="mt-1 font-semibold text-slate-900">{p.headline}</h3>
          <p className="mt-0.5 text-sm text-slate-600 max-w-3xl">{p.pitch}</p>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            {p.facts.map(([Icon, text]) => <li key={text} className="inline-flex items-center gap-1"><Icon size={13} className="text-slate-400" />{text}</li>)}
          </ul>
        </div>
        <div className="shrink-0 flex flex-col items-start sm:items-end gap-1">
          <a href={p.url} target="_blank" rel="noopener noreferrer sponsored"
            className="inline-flex items-center gap-1.5 text-sm font-semibold rounded-xl px-4 py-2.5 bg-slate-900 text-white hover:bg-slate-800">
            Browse {p.name} roles<ArrowUpRight size={16} /></a>
          <span className="text-[11px] text-slate-400">Opens {p.name}. Referral link: Baalebos may earn a reward.</span>
        </div>
      </div>
    </aside>
  ));
}
