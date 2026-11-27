import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';

// Draws each PDF page on a canvas with pdf.js, so previews work on iPhone and
// Android browsers, which often show nothing for a PDF inside an <iframe>.
// pdf.js (legacy build, for older mobile browsers) loads only when a preview opens.
// Falls back to the browser's own viewer if pdf.js cannot load. `src` is a blob: or object URL.
export default function PdfPreview({ src, title = 'PDF preview', className = '', maxPages = 6 }) {
  const holder = useRef(null);
  const [state, setState] = useState('loading');     // loading | ready | fallback
  const [pages, setPages] = useState(0);

  useEffect(() => {
    if (!src) return undefined;
    let cancelled = false;
    let doc = null;
    setState('loading');
    (async () => {
      try {
        const [pdfjs, worker] = await Promise.all([
          import('pdfjs-dist/legacy/build/pdf.mjs'),
          import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'),
        ]);
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
        doc = await pdfjs.getDocument({ url: src, isEvalSupported: false }).promise;
        if (cancelled) return;
        const box = holder.current;
        if (!box) return;
        box.replaceChildren();
        const count = Math.min(doc.numPages, maxPages);
        setPages(doc.numPages);
        const width = Math.max(280, box.clientWidth || 600);
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        for (let n = 1; n <= count; n += 1) {
          const page = await doc.getPage(n);
          if (cancelled) return;
          const base = page.getViewport({ scale: 1 });
          const viewport = page.getViewport({ scale: (width / base.width) * ratio });
          const canvas = document.createElement('canvas');
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.style.width = '100%';
          canvas.style.height = 'auto';
          canvas.className = 'block bg-white shadow-sm rounded-sm';
          canvas.setAttribute('role', 'img');
          canvas.setAttribute('aria-label', `${title}, page ${n} of ${doc.numPages}`);
          box.appendChild(canvas);
          await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
        }
        if (!cancelled) setState('ready');
      } catch {
        if (!cancelled) setState('fallback');
      }
    })();
    return () => { cancelled = true; if (doc) doc.destroy(); };
  }, [src, maxPages, title]);

  return (
    <div className={className}>
      {state === 'fallback' ? (
        <iframe src={`${src}#toolbar=0&navpanes=0&view=FitH`} title={title} className="w-full h-[70vh] rounded-xl border border-slate-200 bg-white" />
      ) : (
        <div className="relative">
          {state === 'loading' && <div className="absolute inset-0 grid place-items-center"><Loader2 className="animate-spin text-slate-400" aria-label="Loading preview" /></div>}
          <div ref={holder} className="space-y-3 min-h-[200px]" />
        </div>
      )}
      <p className="mt-2 text-xs text-slate-500">
        {pages > maxPages ? `Showing the first ${maxPages} of ${pages} pages. ` : ''}
        <a href={src} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-emerald-700 hover:underline">
          Open PDF <ExternalLink size={12} /></a>
      </p>
    </div>
  );
}
