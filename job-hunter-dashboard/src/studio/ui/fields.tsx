// Small, accessible form pieces shared by the Studio editor tabs.
import { useEffect, useId, useState } from 'react';
import type { ReactNode } from 'react';
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';

const input = 'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 ' +
  'focus:border-[#1F4E79] focus:outline-none focus:ring-2 focus:ring-[#1F4E79]/15';

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
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">
          <Plus size={14} /> {addLabel}
        </button>
      </div>
      {items.map((item, i) => (
        <div key={i} className="border-t border-slate-200 pt-3 space-y-3">
          <div className="flex items-center gap-2">
            <p className="flex-1 truncate text-xs font-semibold text-slate-500">{summary(item) || `Entry ${i + 1}`}</p>
            <button type="button" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)} className="p-1 rounded hover:bg-slate-100 disabled:opacity-30"><ArrowUp size={14} /></button>
            <button type="button" aria-label="Move down" disabled={i === items.length - 1} onClick={() => move(i, 1)} className="p-1 rounded hover:bg-slate-100 disabled:opacity-30"><ArrowDown size={14} /></button>
            <button type="button" aria-label="Remove" onClick={() => onChange(items.filter((_, n) => n !== i))} className="p-1 rounded text-slate-500 hover:bg-slate-100 hover:text-rose-600"><Trash2 size={14} /></button>
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

/** A list typed one item per line (core competencies, soft skills). Blank lines are ignored in the resume. */
export function LineList({ label, items, onChange, max, hint, placeholder }: {
  label: string; items: string[]; onChange: (v: string[]) => void; max: number; hint?: string; placeholder?: string;
}) {
  const count = items.filter(i => i.trim()).length;
  return (
    <TextArea label={`${label} (${count}/${max})`} rows={Math.min(10, Math.max(4, items.length + 1))} value={items.join('\n')}
      placeholder={placeholder} hint={hint ?? 'One per line.'}
      onChange={v => onChange(v.split('\n').map(l => l.replace(/^\s*[-•*|]\s?/, '')).slice(0, max))} />
  );
}

/** Skills typed as a comma-separated list; stored as separate items. */
export function CommaField({ label, items, onChange, placeholder, max }: {
  label: string; items: string[]; onChange: (v: string[]) => void; placeholder?: string; max: number;
}) {
  const joined = items.join(', ');
  const [draft, setDraft] = useState(joined);
  const split = (v: string) => v.split(',').map(s => s.trim()).filter(Boolean).slice(0, max);
  // Follow outside changes (another tab, reset) without fighting the person's typing.
  useEffect(() => { if (split(draft).join(', ') !== joined) setDraft(joined); }, [joined]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Field label={label} value={draft} placeholder={placeholder} maxLength={2000}
      hint={`Separate skills with commas (up to ${max}).`}
      onChange={v => { setDraft(v); onChange(split(v)); }} />
  );
}
