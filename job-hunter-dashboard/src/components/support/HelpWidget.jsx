import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowUpRight, LifeBuoy, X } from 'lucide-react';
import SupportForm from './SupportForm';

// Floating "Help" button on every dashboard page. Opens a small panel with the
// support form; the current page and browser are attached automatically.
export default function HelpWidget() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return undefined;
    panelRef.current?.querySelector('select, input:not([type=hidden]):not(.hidden), textarea')?.focus();
    const onKey = (e) => { if (e.key === 'Escape') { setOpen(false); buttonRef.current?.focus(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  if (pathname === '/help') return null;
  return (
    <>
      {open && (
        <div ref={panelRef} role="dialog" aria-modal="false" aria-labelledby="help-widget-title"
          className="fixed z-40 bottom-20 right-4 left-4 sm:left-auto sm:w-[380px] max-h-[calc(100vh-7rem)] overflow-y-auto bg-white border border-slate-200 rounded-2xl shadow-2xl">
          <div className="sticky top-0 bg-white px-5 pt-4 pb-3 border-b border-slate-100 flex items-start justify-between gap-3">
            <div>
              <h2 id="help-widget-title" className="font-semibold text-slate-900">Help &amp; support</h2>
              <p className="text-xs text-slate-500">Questions, problems or feedback. We usually reply within one business day.</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close help" className="p-1 rounded-lg hover:bg-slate-100"><X size={18} /></button>
          </div>
          <div className="p-5">
            <SupportForm compact />
            <Link to="/help" className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-800">
              Common questions and my requests<ArrowUpRight size={14} /></Link>
          </div>
        </div>
      )}
      <button ref={buttonRef} type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-label={open ? 'Close help' : 'Help and support'}
        className="fixed z-40 bottom-4 right-4 inline-flex items-center gap-2 rounded-full bg-slate-900 text-white shadow-lg px-4 py-3 text-sm font-semibold hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2">
        {open ? <X size={18} /> : <LifeBuoy size={18} />}<span className="hidden sm:inline">{open ? 'Close' : 'Help'}</span>
      </button>
    </>
  );
}
