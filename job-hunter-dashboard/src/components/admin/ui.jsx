import { useEffect, useRef, useState } from 'react';
import { Loader2, MoreHorizontal, X } from 'lucide-react';

export const card = 'bg-white border border-slate-200 rounded-2xl';

const TONES = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200', red: 'bg-rose-50 text-rose-700 ring-rose-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200', blue: 'bg-blue-50 text-blue-700 ring-blue-200',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200', slate: 'bg-slate-100 text-slate-700 ring-slate-200',
};

export function Chip({ tone = 'slate', children, title }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ring-1 ring-inset whitespace-nowrap ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function Stat({ label, value, hint, hintTone = 'text-slate-500', icon: Icon, iconTone = 'text-slate-400', highlight }) {
  return (
    <div className={`${card} p-5 ${highlight ? 'ring-1 ring-rose-200 border-rose-200' : ''}`}>
      <div className="flex items-center justify-between text-[13px] text-slate-500">
        <span>{label}</span>{Icon && <Icon size={18} className={iconTone} />}
      </div>
      <div className={`mt-2 text-3xl font-semibold tracking-tight ${highlight ? 'text-rose-600' : 'text-slate-900'}`}>{value}</div>
      {hint && <div className={`mt-1 text-xs ${hintTone}`}>{hint}</div>}
    </div>
  );
}

export function Segmented({ options, value, onChange, size = 'sm' }) {
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5" role="tablist">
      {options.map(([id, label]) => (
        <button key={id} type="button" role="tab" aria-selected={value === id} onClick={() => onChange(id)}
          className={`${size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-1.5 text-sm'} font-medium rounded-md transition-colors ${
            value === id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:text-slate-900'}`}>
          {label}
        </button>
      ))}
    </div>
  );
}

export function SectionHeader({ title, subtitle, children }) {
  return (
    <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Th({ children, right }) {
  return <th className={`px-4 py-2.5 bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500 ${right ? 'text-right' : 'text-left'}`}>{children}</th>;
}

export function Td({ children, className = '', ...rest }) {
  return <td className={`px-4 py-3 border-t border-slate-100 text-[13px] align-middle ${className}`} {...rest}>{children}</td>;
}

export function Empty({ children }) {
  return <div className="px-5 py-10 text-center text-sm text-slate-500">{children}</div>;
}

export function Banner({ tone = 'red', children, onClose }) {
  const tones = { red: 'bg-rose-50 border-rose-200 text-rose-800', amber: 'bg-amber-50 border-amber-200 text-amber-900',
    green: 'bg-emerald-50 border-emerald-200 text-emerald-800', blue: 'bg-blue-50 border-blue-200 text-blue-900' };
  return (
    <div role={tone === 'red' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${tones[tone]}`}>
      <div className="flex-1">{children}</div>
      {onClose && <button type="button" onClick={onClose} aria-label="Dismiss" className="opacity-60 hover:opacity-100"><X size={16} /></button>}
    </div>
  );
}

export function Button({ variant = 'secondary', size = 'md', busy, icon: Icon, children, className = '', ...rest }) {
  const variants = {
    primary: 'bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-300',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300',
    dark: 'bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400',
    secondary: 'bg-white text-slate-800 border border-slate-200 hover:bg-slate-50 disabled:text-slate-400',
    ghost: 'text-slate-600 hover:bg-slate-100',
  };
  const sizes = { sm: 'text-xs px-2.5 py-1.5', md: 'text-sm px-3.5 py-2' };
  return (
    <button type="button" disabled={busy || rest.disabled}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold transition-colors disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {busy ? <Loader2 size={14} className="animate-spin" /> : Icon && <Icon size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  );
}

// Row action menu that closes on outside click / Escape.
export function Menu({ items, label = 'Actions' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (e.type === 'keydown' ? e.key === 'Escape' : !ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  return (
    <div className="relative inline-block text-left" ref={ref}>
      <button type="button" aria-label={label} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(o => !o)}
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"><MoreHorizontal size={18} /></button>
      {open && (
        <div role="menu" className="absolute right-0 mt-1 w-60 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-30">
          {items.filter(Boolean).map(({ label: text, icon: Icon, onClick, tone, divider }) => (
            <button key={text} type="button" role="menuitem" onClick={() => { setOpen(false); onClick(); }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-slate-50 ${divider ? 'border-t border-slate-100' : ''} ${
                tone === 'red' ? 'text-rose-700' : tone === 'amber' ? 'text-amber-700' : 'text-slate-700'}`}>
              {Icon && <Icon size={16} />}{text}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Confirmation dialog with an optional free-text reason.
export function ConfirmDialog({ dialog, onClose }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setReason(dialog?.defaultReason || ''); setError(''); setBusy(false); }, [dialog]);
  if (!dialog) return null;
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { await dialog.onConfirm(reason.trim()); onClose(); }
    catch (err) { setError(dialog.errorText ? dialog.errorText(err) : 'Something went wrong.'); setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <form onSubmit={submit} className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6">
        <h3 id="confirm-title" className="text-lg font-semibold text-slate-900">{dialog.title}</h3>
        {dialog.body && <div className="mt-2 text-sm text-slate-600">{dialog.body}</div>}
        {dialog.reasonLabel && (
          <label className="block mt-4 text-sm font-medium text-slate-700">{dialog.reasonLabel}
            <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3} maxLength={255}
              placeholder={dialog.reasonPlaceholder || ''}
              className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40" />
          </label>
        )}
        {dialog.extra}
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" variant={dialog.tone === 'red' ? 'danger' : 'primary'} busy={busy}>{dialog.confirmLabel || 'Confirm'}</Button>
        </div>
      </form>
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }) {
  if (!total) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  return (
    <div className="px-5 py-3 text-xs text-slate-500 flex items-center justify-between border-t border-slate-100">
      <span>Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}</span>
      <div className="flex gap-1">
        <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <Button size="sm" disabled={last >= total} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

export function Spinner() {
  return <div className="py-16 flex justify-center"><Loader2 className="animate-spin text-emerald-600" size={28} /></div>;
}

export function SearchInput({ value, onChange, onSubmit, placeholder, width = 'w-64' }) {
  return (
    <form onSubmit={e => { e.preventDefault(); onSubmit?.(); }} className="relative">
      <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder}
        className={`${width} pl-3 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/40`} />
    </form>
  );
}

export function Select({ value, onChange, options, label }) {
  return (
    <select aria-label={label} value={value} onChange={e => onChange(e.target.value)}
      className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/40">
      {options.map(([id, text]) => <option key={id} value={id}>{text}</option>)}
    </select>
  );
}
