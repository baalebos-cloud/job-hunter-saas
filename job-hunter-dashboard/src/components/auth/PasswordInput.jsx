/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

// Password field with a Show/Hide button, so people can check what they typed
// (fewer mistyped passwords, forgotten logins and duplicate accounts).
export default function PasswordInput({ value, onChange, className = '', accent = 'hover:text-emerald-400', ...rest }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input {...rest} type={visible ? 'text' : 'password'} value={value} onChange={onChange}
        className={`${className} pr-20`} autoCapitalize="none" autoCorrect="off" spellCheck={false} />
      <button type="button" onClick={() => setVisible(v => !v)} aria-pressed={visible}
        aria-label={visible ? 'Hide password' : 'Show password'}
        className={`absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-black uppercase tracking-wider text-slate-400 ${accent} transition-colors`}>
        {visible ? <EyeOff size={15} /> : <Eye size={15} />}{visible ? 'Hide' : 'Show'}
      </button>
    </div>
  );
}
