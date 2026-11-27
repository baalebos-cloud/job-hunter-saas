import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Loader2 } from 'lucide-react';
import { errorText } from '../../lib/session';
import PublicPage from './PublicPage';
import LegalText from './LegalText';
import SEO from '../SEO';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const DOCS = [['terms', 'Terms'], ['privacy', 'Privacy'], ['cookies', 'Cookies'], ['refunds', 'Refunds'], ['acceptable-use', 'Acceptable use']];

// /legal/:slug  The published version of a legal document (or the draft, clearly marked).
export default function LegalPage() {
  const { slug } = useParams();
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    setDoc(null); setError('');
    axios.get(`${API}/legal/${slug}`).then(r => setDoc(r.data)).catch(err => setError(errorText(err, 'This page could not be loaded.')));
  }, [slug]);
  return (
    <PublicPage>
      {doc && <SEO path={`/legal/${slug}`} title={doc.title} description={`${doc.title} for Baalebos.`} />}
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12 grid md:grid-cols-[12rem_minmax(0,1fr)] gap-10">
        <nav aria-label="Legal documents" className="md:sticky md:top-24 self-start flex md:flex-col gap-1 overflow-x-auto text-sm">
          {DOCS.map(([s, label]) => (
            <a key={s} href={`/legal/${s}`} aria-current={s === slug ? 'page' : undefined}
              className={`px-3 py-2 rounded-lg whitespace-nowrap ${s === slug ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{label}</a>))}
        </nav>
        <article className="max-w-3xl">
          {error && <p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
          {!doc && !error && <Loader2 className="animate-spin text-emerald-600" />}
          {doc && <>
            <h1 className="text-4xl font-extrabold tracking-tight">{doc.title}</h1>
            <p className="mt-2 text-sm text-slate-500">{doc.draft ? 'Draft pending legal review' : `Version ${doc.version} · effective ${new Date(doc.published_at).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}`}</p>
            {doc.draft && <p className="mt-4 rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">This document is a draft and has not yet been approved by our legal counsel. Questions: support@baalebo.xyz</p>}
            <div className="mt-8"><LegalText source={doc.body} /></div>
          </>}
        </article>
      </div>
    </PublicPage>
  );
}
