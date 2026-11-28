// Standard PDF export: every word is real, selectable vector text (no screenshots
// or canvas images), so ATS parsers read exactly what the person sees.
import { PDFDocument, PDFFont, PDFPage, StandardFonts, rgb } from 'pdf-lib';
import type { ResumeData, Paper } from './types';
import { PAPER_SIZES, TYPE } from './types';
export { TYPE };
import { needsUnicodeFont, normalizeText, toWinAnsi } from './text';
import { SECTION_TITLES } from './atsAnalyzer';

const NAVY = rgb(0x1f / 255, 0x4e / 255, 0x79 / 255);
const INK = rgb(0.07, 0.07, 0.07);
const MUTED = rgb(0.2, 0.2, 0.2);
const MARGIN_X = 50;
const MARGIN_TOP = 46;
const MARGIN_BOTTOM = 46;
const BODY = TYPE.body;
const LEADING = 1.32;


export interface UnicodeFonts { regular: Uint8Array; bold: Uint8Array }
export interface PdfOptions { paper?: Paper; unicodeFonts?: UnicodeFonts; title?: string }
type Style = 'regular' | 'bold' | 'italic';
export interface Segment { text: string; style?: Style }

interface Fonts { regular: PDFFont; bold: PDFFont; italic: PDFFont; unicode: boolean }

export class Layout {
  page!: PDFPage;
  y = 0;
  readonly width: number;
  readonly height: number;

  constructor(readonly doc: PDFDocument, readonly fonts: Fonts, paper: Paper) {
    [this.width, this.height] = PAPER_SIZES[paper];
    this.addPage();
  }

  get contentWidth() { return this.width - 2 * MARGIN_X; }

  addPage() { this.page = this.doc.addPage([this.width, this.height]); this.y = this.height - MARGIN_TOP; }

  /** Start a new page unless `needed` points still fit: keeps blocks together. */
  ensureSpace(needed: number) { if (this.y - needed < MARGIN_BOTTOM) this.addPage(); }

  font(style: Style = 'regular') { return this.fonts[style]; }

  text(value: string) { return this.fonts.unicode ? normalizeText(value, true) : toWinAnsi(value, true); }

  measure(value: string, size: number, style: Style = 'regular') { return this.font(style).widthOfTextAtSize(this.text(value), size); }

  draw(value: string, x: number, size: number, style: Style = 'regular', color = INK) {
    const text = this.text(value);
    if (text.trim()) this.page.drawText(text, { x, y: this.y, size, font: this.font(style), color });
  }

  centered(value: string, size: number, style: Style = 'regular', color = INK) {
    for (const line of this.wrapPlain(value, size, style, this.contentWidth)) {
      this.ensureSpace(size * LEADING);
      this.y -= size;
      this.draw(line, (this.width - this.measure(line, size, style)) / 2, size, style, color);
      this.y -= size * (LEADING - 1);
    }
  }

  wrapPlain(value: string, size: number, style: Style, maxWidth: number): string[] {
    return this.wrapSegments([{ text: value, style }], size, maxWidth).map(line => line.map(s => s.text).join(''));
  }

  /** Word-wrap rich segments (bold prefix + regular description) into lines that fit maxWidth. */
  wrapSegments(segments: Segment[], size: number, maxWidth: number): Segment[][] {
    const words: Segment[] = [];
    for (const seg of segments) {
      const parts = this.text(seg.text).split(/(\s+)/).filter(p => p !== '');
      for (const part of parts) words.push({ text: part, style: seg.style || 'regular' });
    }
    const lines: Segment[][] = [];
    let line: Segment[] = [];
    let width = 0;
    for (const word of words) {
      const isSpace = /^\s+$/.test(word.text);
      const w = this.font(word.style).widthOfTextAtSize(isSpace ? ' ' : word.text, size);
      if (isSpace) { if (line.length) { line.push({ text: ' ', style: word.style }); width += w; } continue; }
      if (width + w > maxWidth && line.length) {
        while (line.length && line[line.length - 1].text === ' ') line.pop();
        lines.push(line); line = []; width = 0;
      }
      if (w > maxWidth) {           // a single word wider than the line (long URL): break it by characters
        let chunk = '';
        for (const ch of word.text) {
          if (this.font(word.style).widthOfTextAtSize(chunk + ch, size) > maxWidth) { lines.push([{ text: chunk, style: word.style }]); chunk = ''; }
          chunk += ch;
        }
        line = [{ text: chunk, style: word.style }]; width = this.font(word.style).widthOfTextAtSize(chunk, size);
        continue;
      }
      line.push(word); width += w;
    }
    while (line.length && line[line.length - 1].text === ' ') line.pop();
    if (line.length) lines.push(line);
    return lines;
  }

  /** Draw rich text wrapped to the content width, with an optional bullet and hanging indent. */
  drawWrappedRichLine(segments: Segment[], options: { size?: number; bullet?: boolean; indent?: number; color?: typeof INK } = {}) {
    const size = options.size ?? BODY;
    const indent = options.indent ?? (options.bullet ? 12 : 0);
    const x0 = MARGIN_X + indent;
    const lines = this.wrapSegments(segments, size, this.contentWidth - indent);
    lines.forEach((line, n) => {
      this.ensureSpace(size * LEADING);
      this.y -= size;
      if (options.bullet && n === 0) this.draw('•', MARGIN_X + 2, size, 'regular', options.color ?? INK);
      let x = x0;
      for (const seg of this.runs(line)) { this.draw(seg.text, x, size, seg.style, options.color ?? INK); x += this.measure(seg.text, size, seg.style); }
      this.y -= size * (LEADING - 1);
    });
    return lines.length;
  }

  /** Height of a wrapped paragraph, without drawing it. */
  measureRich(segments: Segment[], size = BODY, bullet = false): number {
    const indent = bullet ? 12 : 0;
    return this.wrapSegments(segments, size, this.contentWidth - indent).length * size * LEADING;
  }

  /** Height of a left/right header line, without drawing it. */
  measureLeftRight(left: Segment[], right: string, size: number = TYPE.entry): number {
    const rightWidth = right ? this.measure(right, size, 'italic') + 12 : 0;
    return this.wrapSegments(left, size, this.contentWidth - rightWidth).length * size * LEADING;
  }

  /** Left text and a right-aligned italic date on one baseline; the left side wraps before the date column.
   *  A header that wraps onto several lines is never split across two pages. */
  drawLeftRight(left: Segment[], right: string, size: number = TYPE.entry) {
    const rightWidth = right ? this.measure(right, size, 'italic') + 12 : 0;
    const lines = this.wrapSegments(left, size, this.contentWidth - rightWidth);
    this.ensureSpace(lines.length * size * LEADING);
    lines.forEach((line, n) => {
      this.ensureSpace(size * LEADING);
      this.y -= size;
      let x = MARGIN_X;
      for (const seg of this.runs(line)) { this.draw(seg.text, x, size, seg.style); x += this.measure(seg.text, size, seg.style); }
      if (n === 0 && right) this.draw(right, this.width - MARGIN_X - this.measure(right, size, 'italic'), size, 'italic', MUTED);
      this.y -= size * (LEADING - 1);
    });
  }

  /** Section heading with a full-width rule; reserves room for the first item too (no orphaned headings). */
  heading(title: string, firstItemHeight: number) {
    const size = TYPE.heading;
    this.ensureSpace(size * 1.8 + 6 + firstItemHeight);
    this.y -= 9 + size;
    this.draw(title, MARGIN_X, size, 'bold', NAVY);
    this.y -= 4;
    this.page.drawLine({ start: { x: MARGIN_X, y: this.y }, end: { x: this.width - MARGIN_X, y: this.y }, thickness: 1.25, color: NAVY });
    this.y -= 5;
  }

  gap(points: number) { this.y -= points; }

  /** Join neighbouring words of the same style so each line is drawn as few text runs as possible:
   *  ATS parsers then read whole phrases instead of one word per line. */
  runs(line: Segment[]): Segment[] {
    const out: Segment[] = [];
    for (const seg of line) {
      const last = out[out.length - 1];
      // A space ends the previous run rather than starting the next: text extractors drop a run's
      // leading space, but always read the visible gap a trailing space leaves.
      if (last && (seg.text === ' ' || (last.style || 'regular') === (seg.style || 'regular'))) last.text += seg.text;
      else out.push({ text: seg.text, style: seg.style || 'regular' });
    }
    return out;
  }
}

const clean = (s: string | undefined) => String(s ?? '').replace(/\s+/g, ' ').trim();
const lineHeight = (n = 1, size = BODY) => n * size * LEADING;

function allText(data: ResumeData): string {
  return JSON.stringify(data);
}

async function loadFonts(doc: PDFDocument, data: ResumeData, unicodeFonts?: UnicodeFonts): Promise<Fonts> {
  if (unicodeFonts && needsUnicodeFont(allText(data))) {
    const fontkit = (await import('@pdf-lib/fontkit')).default;
    doc.registerFontkit(fontkit);
    const regular = await doc.embedFont(unicodeFonts.regular, { subset: true });
    const bold = await doc.embedFont(unicodeFonts.bold, { subset: true });
    return { regular, bold, italic: regular, unicode: true };
  }
  return { regular: await doc.embedFont(StandardFonts.Helvetica), bold: await doc.embedFont(StandardFonts.HelveticaBold),
    italic: await doc.embedFont(StandardFonts.HelveticaOblique), unicode: false };
}

/** Build the resume PDF. Returns the file bytes. */
export async function generateResumePdf(data: ResumeData, options: PdfOptions = {}): Promise<Uint8Array> {
  const paper = options.paper ?? 'A4';
  const doc = await PDFDocument.create();
  const fonts = await loadFonts(doc, data, options.unicodeFonts);
  const name = clean(data.fullName) || 'Resume';
  const keywords = [...data.coreCompetencies, ...data.technicalSkills.flatMap(g => g.items)].map(clean).filter(Boolean);
  const safe = (s: string) => (fonts.unicode ? normalizeText(s) : toWinAnsi(s));
  doc.setTitle(safe(options.title || `${name} - Resume`));
  doc.setAuthor(safe(name));
  doc.setSubject(safe(clean(data.headline) || 'Resume'));
  doc.setKeywords(keywords.slice(0, 40).map(safe));
  doc.setCreator('Baalebos Resume Studio');
  doc.setProducer('Baalebos Resume Studio (pdf-lib)');

  const L = new Layout(doc, fonts, paper);
  // Header
  L.centered(name.toUpperCase(), TYPE.name, 'bold', NAVY);
  if (clean(data.headline)) { L.gap(1); L.centered(data.headline, TYPE.headline, 'bold'); }
  const contact1 = [data.location, data.phone, data.email].map(clean).filter(Boolean).join(' | ');
  const contact2 = [data.linkedin, data.github, data.portfolio].map(clean).filter(Boolean).join(' | ');
  if (contact1) { L.gap(1); L.centered(contact1, TYPE.contact, 'regular', MUTED); }
  if (contact2) L.centered(contact2, TYPE.contact, 'regular', MUTED);

  const [SUMMARY, CORE, SOFT, PROJECTS, TECH, EXPERIENCE, EDUCATION, CERTS] = SECTION_TITLES;
  if (clean(data.summary)) { L.heading(SUMMARY, lineHeight(2)); L.drawWrappedRichLine([{ text: data.summary }]); }
  const core = data.coreCompetencies.map(clean).filter(Boolean);
  if (core.length) { L.heading(CORE, lineHeight()); L.drawWrappedRichLine([{ text: core.join(' | ') }]); }
  const soft = data.softSkills.map(clean).filter(Boolean);
  if (soft.length) { L.heading(SOFT, lineHeight()); L.drawWrappedRichLine([{ text: soft.join(' | ') }]); }
  const projects = data.projects.filter(p => clean(p.title));
  if (projects.length) {
    L.heading(PROJECTS, lineHeight(2));
    if (clean(data.projectsIntro)) { L.drawWrappedRichLine([{ text: data.projectsIntro, style: 'italic' }]); L.gap(2); }
    for (const p of projects) {
      L.ensureSpace(lineHeight(2));
      L.drawWrappedRichLine([{ text: clean(p.title), style: 'bold' }, { text: clean(p.tech) ? ` (${clean(p.tech)})` : '' },
        { text: clean(p.description) ? `. ${clean(p.description)}` : '' }], { bullet: true });
      L.gap(1.5);
    }
  }
  const groups = data.technicalSkills.filter(g => g.items.map(clean).filter(Boolean).length);
  if (groups.length) {
    L.heading(TECH, lineHeight());
    for (const g of groups) L.drawWrappedRichLine([{ text: `${clean(g.label)}: `, style: 'bold' }, { text: g.items.map(clean).filter(Boolean).join(', ') }]);
  }
  const roles = data.experience.filter(r => clean(r.role) || clean(r.company));
  if (roles.length) {
    // A role's header (however many lines it wraps to) always starts on the same page as its first bullet.
    const roleHeader = (r: typeof roles[number]): Segment[] => {
      const where = [r.company, r.location].map(clean).filter(Boolean).join(' · ');
      return [{ text: `${clean(r.role)}${where ? ` | ${where}` : ''}`, style: 'bold' }];
    };
    const roleStart = (r: typeof roles[number]) => {
      const first = r.bullets.map(clean).find(Boolean);
      return L.measureLeftRight(roleHeader(r), clean(r.dates)) + (first ? L.measureRich([{ text: first }], BODY, true) : 0);
    };
    L.heading(EXPERIENCE, roleStart(roles[0]));
    roles.forEach((r, n) => {
      if (n) L.gap(4);
      L.ensureSpace(roleStart(r));
      L.drawLeftRight(roleHeader(r), clean(r.dates));
      for (const b of r.bullets.map(clean).filter(Boolean)) L.drawWrappedRichLine([{ text: b }], { bullet: true });
    });
  }
  const schools = data.education.filter(e => clean(e.degree) || clean(e.institution));
  if (schools.length) {
    const school = (e: typeof schools[number]): Segment[] =>
      [{ text: `${clean(e.degree)}${clean(e.institution) ? ` | ${clean(e.institution)}` : ''}`, style: 'bold' }];
    L.heading(EDUCATION, L.measureLeftRight(school(schools[0]), clean(schools[0].date)));
    for (const e of schools) L.drawLeftRight(school(e), clean(e.date));
  }
  const certs = data.certifications.filter(c => clean(c.name));
  if (certs.length) {
    const cert = (c: typeof certs[number]): Segment[] =>
      [{ text: '\u2022  ' }, { text: `${clean(c.name)}${clean(c.issuer) ? `, ${clean(c.issuer)}` : ''}`, style: 'bold' }];
    L.heading(CERTS, L.measureLeftRight(cert(certs[0]), clean(certs[0].date), BODY));
    for (const c of certs) L.drawLeftRight(cert(c), clean(c.date), BODY);
  }
  return doc.save();
}
