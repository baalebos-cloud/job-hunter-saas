/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import { ArrowDown, ArrowUp, Copy, ListChecks, Plus, Trash2 } from 'lucide-react';

import { ALWAYS, CHOICE, LEVELS, MAX_QUESTIONS, QUESTION_TYPES, STANDARD_FIELDS, defaultApplicationForm, newId } from '../../lib/applicationForm';

const input = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10';

export default function ApplicationFormBuilder({ value, onChange, copyFrom = [] }) {
  const form = value || defaultApplicationForm();
  const set = (patch) => onChange({ ...form, ...patch });
  const setLevel = (key, level) => set({ standard: { ...form.standard, [key]: level } });
  const setQuestion = (i, patch) => set({ questions: form.questions.map((q, n) => (n === i ? { ...q, ...patch } : q)) });
  const move = (i, step) => {
    const next = [...form.questions];
    [next[i], next[i + step]] = [next[i + step], next[i]];
    set({ questions: next });
  };
  const add = () => set({ questions: [...form.questions, { id: newId(), label: '', type: 'short_text', required: false, options: [], help: '' }] });
  const copy = (jobId) => {
    const source = copyFrom.find(j => String(j.id) === jobId)?.application_form;
    if (source) onChange({ ...source, questions: (source.questions || []).map(q => ({ ...q, id: newId() })) });
  };
  const authOn = (form.standard.work_authorization || 'off') !== 'off';

  return (
    <div className="space-y-5">
      {copyFrom.length > 0 && (
        <label className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <Copy size={15} className="text-slate-400" />Start from another job&apos;s form
          <select defaultValue="" onChange={e => { copy(e.target.value); e.target.value = ''; }} aria-label="Copy the application form from another job"
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm">
            <option value="">Choose a job…</option>
            {copyFrom.map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
        </label>)}

      <div>
        <p className="text-sm font-medium text-slate-700">Always included</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {ALWAYS.map(a => <span key={a} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{a}</span>)}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-slate-700">Standard details</p>
        <ul className="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200">
          {STANDARD_FIELDS.map(([key, label]) => {
            const level = form.standard[key] || 'off';
            return (
              <li key={key} className="px-3.5 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm text-slate-800">{label}</span>
                  <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-slate-100 p-0.5">
                    {LEVELS.map(([id, text]) => (
                      <button key={id} type="button" role="radio" aria-checked={level === id} onClick={() => setLevel(key, id)}
                        className={`rounded-md px-2.5 py-1 text-xs font-medium ${level === id ? (id === 'required' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-900 shadow-sm') : 'text-slate-500 hover:text-slate-800'}`}>{text}</button>))}
                  </div>
                </div>
                {key === 'work_authorization' && authOn && (
                  <input className={`${input} mt-2`} aria-label="Country for work authorisation" placeholder="Which country? e.g. United Kingdom"
                    value={form.authorization_country || ''} onChange={e => set({ authorization_country: e.target.value })} maxLength={60} />)}
              </li>);
          })}
        </ul>
      </div>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-slate-700">Your questions for this job <span className="font-normal text-slate-500">({form.questions.length}/{MAX_QUESTIONS})</span></p>
          <button type="button" onClick={add} disabled={form.questions.length >= MAX_QUESTIONS}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <Plus size={15} />Add question</button>
        </div>
        {form.questions.length === 0 ? (
          <p className="mt-2 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500 flex gap-2">
            <ListChecks size={16} className="shrink-0 mt-0.5" />Add the questions this role needs, for example a certification, a clearance, shift availability or a link to their work.</p>
        ) : (
          <ol className="mt-2 space-y-3">
            {form.questions.map((q, i) => (
              <li key={q.id} className="rounded-xl border border-slate-200 p-3.5 space-y-2.5">
                <div className="flex items-start gap-2">
                  <span className="mt-2 text-xs font-semibold text-slate-400 w-5">{i + 1}.</span>
                  <input className={input} aria-label={`Question ${i + 1}`} placeholder="Question, e.g. Do you hold a valid AWS certification?"
                    value={q.label} maxLength={300} onChange={e => setQuestion(i, { label: e.target.value })} />
                  <div className="flex shrink-0">
                    <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move question ${i + 1} up`} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 disabled:opacity-30"><ArrowUp size={15} /></button>
                    <button type="button" onClick={() => move(i, 1)} disabled={i === form.questions.length - 1} aria-label={`Move question ${i + 1} down`} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 disabled:opacity-30"><ArrowDown size={15} /></button>
                    <button type="button" onClick={() => set({ questions: form.questions.filter((_, n) => n !== i) })} aria-label={`Delete question ${i + 1}`} className="p-2 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={15} /></button>
                  </div>
                </div>
                <div className="pl-7 flex flex-wrap items-center gap-3">
                  <select aria-label={`Answer type for question ${i + 1}`} value={q.type} onChange={e => setQuestion(i, { type: e.target.value })}
                    className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm">
                    {QUESTION_TYPES.map(([id, text]) => <option key={id} value={id}>{text}</option>)}
                  </select>
                  <label className="inline-flex items-center gap-1.5 text-sm text-slate-700">
                    <input type="checkbox" className="accent-emerald-600" checked={!!q.required} onChange={e => setQuestion(i, { required: e.target.checked })} />Required</label>
                </div>
                {CHOICE.has(q.type) && (
                  <div className="pl-7">
                    <textarea rows={3} className={input} aria-label={`Choices for question ${i + 1}`} placeholder={'One choice per line\nAWS\nGoogle Cloud\nAzure'}
                      value={(q.options || []).join('\n')} onChange={e => setQuestion(i, { options: e.target.value.split('\n') })} />
                    <p className="mt-1 text-xs text-slate-500">One choice per line, 2 to 20 choices.</p>
                  </div>)}
                <div className="pl-7">
                  <input className={input} aria-label={`Help text for question ${i + 1}`} placeholder="Help text for the candidate (optional)"
                    value={q.help || ''} maxLength={300} onChange={e => setQuestion(i, { help: e.target.value })} />
                </div>
              </li>))}
          </ol>)}
        <p className="mt-2 text-xs text-slate-500">Answers are shown to you with each application. Nobody is rejected automatically.</p>
      </div>
    </div>
  );
}
