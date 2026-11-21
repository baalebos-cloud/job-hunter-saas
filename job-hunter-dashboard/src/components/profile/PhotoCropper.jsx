import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, RotateCw, X, ZoomIn, ZoomOut } from 'lucide-react';

const VIEW = 288;        // on-screen crop square (CSS px)
const OUTPUT = 512;      // saved image size

// Circular crop with drag to reposition, zoom and rotate. Returns a 512x512 JPEG blob.
export default function PhotoCropper({ file, onCancel, onSave, saving, error }) {
  const canvasRef = useRef(null);
  const previewRef = useRef(null);
  const drag = useRef(null);
  const [image, setImage] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    let active = true;   // ignore late events from an image whose URL was already revoked
    const url = URL.createObjectURL(file);
    const img = new Image();
    setImage(null); setLoadError('');
    img.onload = () => { if (active) setImage(img); };
    img.onerror = () => { if (active) setLoadError('This file could not be read as an image. Choose a JPG, PNG or WebP photo.'); };
    img.src = url;
    return () => { active = false; URL.revokeObjectURL(url); };
  }, [file]);

  // Scale at zoom 1 so the (rotated) image covers the crop square.
  const coverScale = useCallback(() => {
    if (!image) return 1;
    const sideways = rotation % 180 !== 0;
    const w = sideways ? image.naturalHeight : image.naturalWidth;
    const h = sideways ? image.naturalWidth : image.naturalHeight;
    return Math.max(VIEW / w, VIEW / h);
  }, [image, rotation]);

  // Keep the crop square covered: limit how far the image can move.
  const clamp = useCallback((next, z = zoom) => {
    if (!image) return next;
    const sideways = rotation % 180 !== 0;
    const scale = coverScale() * z;
    const w = (sideways ? image.naturalHeight : image.naturalWidth) * scale;
    const h = (sideways ? image.naturalWidth : image.naturalHeight) * scale;
    const maxX = Math.max(0, (w - VIEW) / 2);
    const maxY = Math.max(0, (h - VIEW) / 2);
    return { x: Math.min(maxX, Math.max(-maxX, next.x)), y: Math.min(maxY, Math.max(-maxY, next.y)) };
  }, [image, rotation, zoom, coverScale]);

  const draw = useCallback((canvas, size) => {
    if (!canvas || !image) return;
    const ratio = size / VIEW;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, size, size);
    ctx.save();
    ctx.translate(size / 2 + offset.x * ratio, size / 2 + offset.y * ratio);
    ctx.rotate((rotation * Math.PI) / 180);
    const scale = coverScale() * zoom * ratio;
    ctx.scale(scale, scale);
    ctx.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2);
    ctx.restore();
  }, [image, offset, rotation, zoom, coverScale]);

  useEffect(() => {
    const dpr = window.devicePixelRatio || 1;
    for (const [ref, css] of [[canvasRef, VIEW], [previewRef, 112]]) {
      const canvas = ref.current;
      if (!canvas) continue;
      canvas.width = css * dpr; canvas.height = css * dpr;
      draw(canvas, css * dpr);
    }
  }, [draw]);

  const onPointerDown = (e) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, start: offset };
  };
  const onPointerMove = (e) => {
    if (!drag.current) return;
    const { x, y, start } = drag.current;
    setOffset(clamp({ x: start.x + e.clientX - x, y: start.y + e.clientY - y }));
  };
  const onPointerUp = () => { drag.current = null; };
  const onKeyDown = (e) => {
    const step = e.shiftKey ? 20 : 5;
    const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (moves[e.key]) { e.preventDefault(); setOffset(o => clamp({ x: o.x + moves[e.key][0], y: o.y + moves[e.key][1] })); }
  };
  const setZoomClamped = (z) => { setZoom(z); setOffset(o => clamp(o, z)); };
  const rotate = () => { setRotation(r => (r + 90) % 360); setOffset({ x: 0, y: 0 }); };

  const save = () => {
    const canvas = document.createElement('canvas');
    canvas.width = OUTPUT; canvas.height = OUTPUT;
    draw(canvas, OUTPUT);
    canvas.toBlob(blob => blob && onSave(blob), 'image/jpeg', 0.92);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" role="dialog" aria-modal="true" aria-labelledby="crop-title">
      <div className="w-full max-w-xl bg-white rounded-2xl shadow-xl p-6">
        <div className="flex items-center justify-between">
          <h2 id="crop-title" className="text-lg font-semibold text-slate-900">Crop your profile photo</h2>
          <button type="button" onClick={onCancel} aria-label="Close" className="p-1 rounded-lg hover:bg-slate-100"><X size={20} /></button>
        </div>
        {loadError ? <p role="alert" className="mt-4 text-sm text-rose-700 bg-rose-50 rounded-xl p-4">{loadError}</p> : (
          <>
            <div className="mt-4 flex flex-col sm:flex-row items-center gap-6">
              <div className="relative shrink-0 rounded-xl overflow-hidden bg-slate-800" style={{ width: VIEW, height: VIEW }}>
                {!image && <div className="absolute inset-0 grid place-items-center"><Loader2 className="animate-spin text-white" /></div>}
                <canvas ref={canvasRef} style={{ width: VIEW, height: VIEW, touchAction: 'none' }} tabIndex={0}
                  aria-label="Photo crop area. Drag or use the arrow keys to reposition."
                  className="cursor-move focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
                  onKeyDown={onKeyDown} />
                <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(circle at center, transparent 0 141px, rgba(15,23,42,.55) 142px)' }} />
                <div className="pointer-events-none absolute inset-[3px] rounded-full ring-2 ring-white/90" />
              </div>
              <div className="text-center">
                <canvas ref={previewRef} style={{ width: 112, height: 112 }} className="rounded-full ring-2 ring-slate-200" aria-hidden="true" />
                <div className="text-xs text-slate-500 mt-2">Preview</div>
              </div>
            </div>
            <div className="mt-5 flex items-center gap-3 text-slate-600">
              <ZoomOut size={18} aria-hidden="true" />
              <input type="range" min="1" max="3" step="0.01" value={zoom} onChange={e => setZoomClamped(Number(e.target.value))}
                aria-label="Zoom" className="flex-1 accent-emerald-600" />
              <ZoomIn size={18} aria-hidden="true" />
              <button type="button" onClick={rotate} className="ml-2 inline-flex items-center gap-1 text-sm font-medium hover:text-slate-900"><RotateCw size={16} />Rotate</button>
            </div>
          </>
        )}
        {error && <p role="alert" className="mt-4 text-sm text-rose-700 bg-rose-50 rounded-xl p-3">{error}</p>}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-slate-500">JPG, PNG or WebP up to 5 MB. Saved as a 512 × 512 image.</span>
          <div className="flex gap-2">
            <button type="button" onClick={onCancel} className="text-sm font-semibold rounded-xl px-4 py-2 border border-slate-200 hover:bg-slate-50">Cancel</button>
            <button type="button" onClick={save} disabled={!image || saving}
              className="inline-flex items-center gap-2 text-sm font-semibold rounded-xl px-4 py-2 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60">
              {saving && <Loader2 size={16} className="animate-spin" />}Save photo</button>
          </div>
        </div>
      </div>
    </div>
  );
}
