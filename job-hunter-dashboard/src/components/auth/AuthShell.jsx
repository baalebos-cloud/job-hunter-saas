/* eslint-disable react/prop-types -- the project does not use the prop-types package */
// Shared frame for sign-in and sign-up pages: the landing page's look (warm paper,
// wordmark, ink buttons), the form on the left and a quiet side panel on the right.


export function ErrorNote({ children }) {
  return <div role="alert" className="mb-6 rounded-[10px] border border-rose-200 bg-rose-50 px-4 py-3 text-[14px] text-rose-800">{children}</div>;
}

export function Spinner() {
  return (
    <svg className="inline-block animate-spin w-4 h-4 mr-2 -mt-0.5" fill="none" viewBox="0 0 24 24" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export default function AuthShell({ children, aside, asideTone = 'sand', employer = false, wide = false, title, intro }) {
  const dark = asideTone === 'ink';
  return (
    <div className={`auth-shell min-h-screen min-h-[100dvh] bg-[#fbfaf7] text-[#0b1324] grid ${wide ? 'lg:grid-cols-[minmax(0,1.15fr)_minmax(0,.85fr)]' : 'lg:grid-cols-2'}`}
      style={{ fontFamily: "'Inter Tight', Inter, Arial, sans-serif" }}>
      <main className="flex flex-col px-5 sm:px-12 lg:px-20 py-8 min-w-0">
        <div className="flex items-center gap-3">
          <a href="/" className="text-[22px] font-extrabold tracking-tight">baalebos<span className="text-emerald-500">.</span></a>
          {employer && <span className="rounded-full border border-slate-300 px-2.5 py-0.5 text-[12px] font-semibold text-slate-700">For employers</span>}
        </div>
        <div className={`w-full ${wide ? 'max-w-[520px] py-12' : 'max-w-[400px] my-auto py-12'}`}>
          <h1 className="text-[32px] sm:text-[34px] leading-tight font-bold tracking-tight">{title}</h1>
          {intro && <p className="mt-2 text-[15.5px] text-slate-600">{intro}</p>}
          <div className="mt-8">{children}</div>
        </div>
        <p className="mt-auto text-[12.5px] text-slate-500">
          <a href="/legal/terms" className="hover:text-slate-800">Terms</a> · <a href="/legal/privacy" className="hover:text-slate-800">Privacy</a> · <a href="/help" className="hover:text-slate-800">Help</a>
        </p>
      </main>
      <aside className={`hidden lg:flex flex-col ${wide ? 'py-24' : 'justify-center'} px-14 xl:px-20 ${dark ? 'bg-[#0b1324] text-white' : 'bg-[#f1eee6] border-l border-[#e7e3da]'}`}>
        <div className={`max-w-[440px] ${wide ? 'sticky top-24' : ''}`}>{aside}</div>
      </aside>
    </div>
  );
}

export function AsideEyebrow({ children, dark = false }) {
  return <p className={`text-[13px] font-semibold uppercase tracking-[.14em] ${dark ? 'text-emerald-300' : 'text-emerald-800'}`}>{children}</p>;
}

export function ExampleList({ title, rows, dark = false }) {
  return (
    <div className={`mt-10 rounded-md p-6 ${dark ? 'bg-white text-[#0b1324]' : 'border border-[#e2ddd2] bg-white shadow-[0_24px_50px_-30px_rgba(11,19,36,.35)]'}`}>
      <div className="flex items-center justify-between text-[13px] text-slate-500"><span>{title}</span><span>example</span></div>
      <ul className="mt-4 divide-y divide-slate-100 text-[14.5px]">
        {rows.map(([left, right, tone]) => (
          <li key={left} className="flex justify-between gap-4 py-3"><span>{left}</span>
            <span className={`font-semibold ${tone === 'amber' ? 'text-amber-700' : 'text-emerald-700'}`}>{right}</span></li>
        ))}
      </ul>
    </div>
  );
}
