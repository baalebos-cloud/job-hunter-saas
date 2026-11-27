// Unicode fonts for names and text Helvetica cannot draw (e.g. Yoruba "Ọ").
// Loaded only when a resume needs them; served from /fonts/dejavu (licence in LICENSE.txt there).
import type { UnicodeFonts } from './pdfEngine';

let cached: Promise<UnicodeFonts> | null = null;

export function loadUnicodeFonts(base = '/fonts/dejavu'): Promise<UnicodeFonts> {
  cached ??= Promise.all(['DejaVuSans.ttf', 'DejaVuSans-Bold.ttf'].map(async name => {
    const response = await fetch(`${base}/${name}`);
    if (!response.ok) throw new Error(`Font ${name} could not be loaded`);
    return new Uint8Array(await response.arrayBuffer());
  })).then(([regular, bold]) => ({ regular, bold })).catch(err => { cached = null; throw err; });
  return cached;
}
