/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useState } from 'react';

// Pick several values: choose a suggestion or type your own, press Enter or comma
// to add, × or Backspace to remove. `normalize` turns typed text into the stored
// value (or null when it is not allowed, e.g. a country that is not on the list).
export default function ChipInput({ id, values, onChange, suggestions, max, placeholder, normalize = v => v.trim() || null,
  onInvalid, className = '', chipClass = '' }) {
  const [text, setText] = useState('');
  const add = (raw) => {
    const value = normalize(raw);
    if (!raw.trim()) return true;
    if (!value) { onInvalid?.(raw); return false; }
    if (values.some(v => v.toLowerCase() === value.toLowerCase())) { setText(''); return true; }
    if (values.length >= max) { onInvalid?.(raw, 'max'); return false; }
    onChange([...values, value]); setText('');
    return true;
  };
  const onKeyDown = (e) => {
    if ((e.key === 'Enter' || e.key === ',') && text.trim()) { e.preventDefault(); add(text); }
    else if (e.key === 'Backspace' && !text && values.length) onChange(values.slice(0, -1));
  };
  const onInput = (value) => {
    // Picking from the suggestion list fills the whole value at once: add it straight away.
    if (suggestions.some(s => s === value)) { add(value); return; }
    setText(value.replace(/,$/, ''));
    if (value.endsWith(',')) add(value.slice(0, -1));
  };
  const full = values.length >= max;
  return (
    <div className={className} onClick={() => document.getElementById(id)?.focus()}>
      <div className="flex flex-wrap items-center gap-1.5">
        {values.map(v => (
          <span key={v} className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium ${chipClass}`}>
            {v}<button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(values.filter(x => x !== v))} className="opacity-70 hover:opacity-100">×</button>
          </span>))}
        <input id={id} list={`${id}-options`} value={text} disabled={full} autoComplete="off" maxLength={80}
          placeholder={full ? `Up to ${max}` : (values.length ? 'Add another' : placeholder)}
          onChange={e => onInput(e.target.value)} onKeyDown={onKeyDown} onBlur={() => text.trim() && add(text)}
          className="flex-1 min-w-[8rem] bg-transparent outline-none text-[15px] placeholder:text-[#9a968c] disabled:cursor-not-allowed" />
      </div>
      <datalist id={`${id}-options`}>{suggestions.map(s => <option key={s} value={s} />)}</datalist>
    </div>
  );
}
