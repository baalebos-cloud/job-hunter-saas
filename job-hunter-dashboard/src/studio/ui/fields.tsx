// Small, accessible form pieces shared by the Studio editor tabs.
import { useId, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react';

const input = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 ' +
  'focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20';

export function Field({ label, value, onChange, placeholder, hint, type = 'text', maxLength }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; hint?: string; type?: string; maxLength?: number;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-slate-700 mb-1">{label}</label>
      <input id={id} type={type} className={input} value={value} placeholder={placeholder} maxLength={maxLength}
        onChange={e => onChange(e.target.value)} />
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function TextArea({ label, value, onChange, placeholder, rows = 4, hint, maxLength }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; rows?: number; hint?: string; maxLength?: number;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-slate-700 mb-1">{label}</label>
      <textarea id={id} rows={rows} className={`${input} resize-y leading-relaxed`} value={value} placeholder={placeholder}
        maxLength={maxLength} onChange={e => onChange(e.target.value)} />
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

/** A list of short phrases (skills, competencies). Enter or comma adds; pasting a "a, b | c" list splits it. */
export function ChipList({ label, items, onChange, placeholder, max, hint }: {
  label: string; items: string[]; onChange: (v: string[]) => void; placeholder?: string; max: number; hint?: string;
}) {
  const id = useId();
  const [draft, setDraft] = useState('');
  const add = (raw: string) => {
    const parts = raw.split(/[,|\n]/).map(s => s.trim()).filter(Boolean);
    const seen = new Set(items.map(i => i.toLowerCase()));
    const next = [...items];
    for (const p of parts) if (!seen.has(p.toLowerCase()) && next.length < max) { next.push(p); seen.add(p.toLowerCase()); }
    onChange(next);
    setDraft('');
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === 'Enter' || e.key === ',') && draft.trim()) { e.preventDefault(); add(draft); }
    else if (e.key === 'Backspace' && !draft && items.length) onChange(items.slice(0, -1));
  };
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-slate-700 mb-1">
        {label} <span className="font-normal text-slate-400">({items.length}/{max})</span>
      </label>
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-slate-300 bg-white p-2 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20">
        {items.map((item, i) => (
          <span key={`${item}-${i}`} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-800">
            {item}
            <button type="button" aria-label={`Remove ${item}`} className="text-slate-400 hover:text-rose-600"
              onClick={() => onChange(items.filter((_, n) => n !== i))}><X size={12} /></button>
          </span>
        ))}
        <input id={id} className="min-w-[8rem] flex-1 bg-transparent px-1 py-0.5 text-sm outline-none" value={draft}
          placeholder={items.length >= max ? 'Limit reached' : placeholder} disabled={items.length >= max}
          onChange={e => setDraft(e.target.value)} onKeyDown={onKey} onBlur={() => draft.trim() && add(draft)}
          onPaste={e => { const t = e.clipboardData.getData('text'); if (/[,|\n]/.test(t)) { e.preventDefault(); add(t); } }} />
      </div>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

/** Repeating entries (roles, projects, schools) with move up/down and remove. */
export function Repeater<T>({ title, items, onChange, make, max, render, summary, addLabel }: {
  title: string; items: T[]; onChange: (v: T[]) => void; make: () => T; max: number; addLabel: string;
  render: (item: T, update: (patch: Partial<T>) => void, index: number) => ReactNode; summary: (item: T) => string;
}) {
  const move = (i: number, d: number) => {
    const next = [...items];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onChange(next);
  };
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">{title} <span className="font-normal text-slate-400">({items.length}/{max})</span></h3>
        <button type="button" disabled={items.length >= max} onClick={() => onChange([...items, make()])}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">
          <Plus size={14} /> {addLabel}
        </button>
      </div>
      {items.map((item, i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 space-y-3">
          <div className="flex items-center gap-2">
            <p className="flex-1 truncate text-xs font-semibold text-slate-500">{summary(item) || `Entry ${i + 1}`}</p>
            <button type="button" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)} className="p-1 rounded hover:bg-white disabled:opacity-30"><ArrowUp size={14} /></button>
            <button type="button" aria-label="Move down" disabled={i === items.length - 1} onClick={() => move(i, 1)} className="p-1 rounded hover:bg-white disabled:opacity-30"><ArrowDown size={14} /></button>
            <button type="button" aria-label="Remove" onClick={() => onChange(items.filter((_, n) => n !== i))} className="p-1 rounded text-slate-500 hover:bg-white hover:text-rose-600"><Trash2 size={14} /></button>
          </div>
          {render(item, patch => onChange(items.map((x, n) => (n === i ? { ...x, ...patch } : x))), i)}
        </div>
      ))}
    </section>
  );
}

/** One bullet per line; blank lines are ignored when the PDF is built. */
export function BulletLines({ label, bullets, onChange, max }: { label: string; bullets: string[]; onChange: (v: string[]) => void; max: number }) {
  const value = bullets.join('\n');
  return (
    <TextArea label={label} rows={Math.min(10, Math.max(3, bullets.length + 1))} value={value}
      hint={`One achievement per line (up to ${max}). Start with a verb and keep numbers you can prove.`}
      onChange={v => onChange(v.split('\n').map(l => l.replace(/^\s*[-•*]\s?/, '')).slice(0, max))} />
  );
}
