import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { PDFDocument, PDFName } from 'pdf-lib';
import { analyzeJobDescription, analyzeResumeAts, buildPlainTextResume, containsKeyword } from '../atsAnalyzer';
import { applyRolePreset } from '../presets';
import { generateResumePdf } from '../pdfEngine';
import { needsUnicodeFont, normalizeText, toWinAnsi } from '../text';
import { emptyResume } from '../types';
import { sampleResume } from './fixture';

test('plain text keeps every section in reading order', () => {
  const text = buildPlainTextResume(sampleResume());
  const order = ['JORDAN LEE', 'CAREER SUMMARY', 'CORE COMPETENCIES', 'SOFT SKILLS', 'PROJECTS COMPLETED', 'TECHNICAL SKILLS',
    'PROFESSIONAL EXPERIENCE', 'EDUCATION', 'PROFESSIONAL CERTIFICATIONS'];
  const positions = order.map(t => text.indexOf(t));
  assert.ok(positions.every(p => p >= 0), 'every heading present');
  assert.deepEqual([...positions].sort((a, b) => a - b), positions);
  assert.match(text, /Lagos, Nigeria \| \+234 801 555 0101 \| jordan\.lee@example\.org/);
  assert.match(text, /- Job board scraper \(Python, FastAPI, PostgreSQL\)\. Collects 700\+ listings/);
  assert.match(text, /Automation: Terraform, Ansible, GitHub Actions/);
  assert.ok(!buildPlainTextResume({ ...emptyResume(), fullName: 'A' }).includes('CAREER SUMMARY'), 'empty sections are left out');
});

test('keyword matching respects word boundaries', () => {
  assert.ok(containsKeyword('Python, Java and CI/CD', 'java'));
  assert.ok(!containsKeyword('JavaScript only', 'java'));
  assert.ok(containsKeyword('Built CI/CD pipelines', 'ci/cd'));
  assert.ok(containsKeyword('Node.js services', 'node.js'));
  assert.ok(!containsKeyword('goals', 'go'));
});

test('ATS audit: coverage per group and the five readiness checks', () => {
  const report = analyzeResumeAts(sampleResume());
  const cloud = report.groups.find(g => g.group === 'Cloud & DevOps Infrastructure')!;
  assert.ok(cloud.matched.includes('terraform') && cloud.matched.includes('ci/cd') && cloud.missing.includes('helm'));
  assert.equal(cloud.percent, Math.round((100 * cloud.matched.length) / (cloud.matched.length + cloud.missing.length)));
  const checks = Object.fromEntries(report.checks.map(c => [c.id, c.ok]));
  assert.deepEqual(Object.keys(checks), ['layout', 'sections', 'contact', 'metrics', 'length']);
  assert.equal(checks.contact, true);
  assert.equal(checks.metrics, true);
  assert.equal(checks.length, false, 'the sample is shorter than 350 words');
  const empty = analyzeResumeAts({ ...emptyResume(), fullName: 'A' });
  assert.equal(empty.checks.find(c => c.id === 'sections')!.ok, false);
  assert.match(empty.checks.find(c => c.id === 'contact')!.detail, /location, email/);
});

test('job description: extracts terms, and a matching profile has nothing missing', () => {
  const jd = `We need a Cloud DevOps engineer. You will run Kubernetes on AWS, write Terraform and Ansible, and own CI/CD with
    GitHub Actions and Jenkins. Python and Bash scripting. Linux. Experience with Docker is required. Docker, docker.`;
  const result = analyzeJobDescription(sampleResume(), jd);
  for (const term of ['kubernetes', 'aws', 'terraform', 'ansible', 'ci/cd', 'github actions', 'jenkins', 'python', 'bash', 'linux', 'docker']) {
    assert.ok(result.extractedKeywords.includes(term), term);
  }
  assert.deepEqual(result.missingKeywords, []);
  assert.equal(result.matchPercent, 100);
  const gap = analyzeJobDescription(sampleResume(), 'Helm and ArgoCD on Kubernetes. Helm charts. ArgoCD rollouts.');
  assert.ok(gap.missingKeywords.includes('helm') && gap.missingKeywords.includes('argocd') && gap.matchedKeywords.includes('kubernetes'));
  assert.ok(gap.extractedKeywords.length <= 60);
  assert.deepEqual(analyzeJobDescription(sampleResume(), '  ').extractedKeywords, []);
});

test('role presets re-order evidence but never add or remove anything', () => {
  const base = sampleResume();
  const cloud = applyRolePreset(base, 'cloud');
  assert.equal(cloud.coreCompetencies[0].startsWith('AWS'), true);
  assert.equal(cloud.coreCompetencies.at(-1), 'Team communication');
  assert.equal(cloud.technicalSkills[0].label, 'Automation');
  assert.ok(cloud.experience[0].bullets[0].startsWith('Migrated 40 services'));
  assert.ok(cloud.headline.startsWith('Cloud DevOps Engineer | '));
  const sorted = (d: typeof base) => JSON.stringify([d.coreCompetencies, d.technicalSkills.flatMap(g => g.items), d.experience.flatMap(r => r.bullets),
    d.projects.map(p => p.title)].map(list => [...list].sort()));
  assert.equal(sorted(cloud), sorted(base));
  assert.equal(cloud.summary, base.summary);
  assert.deepEqual(applyRolePreset(base, 'as-is'), base);
  assert.equal(base.coreCompetencies[0], 'Team communication', 'the input is not changed');
});

test('text clean-up keeps letters and normalises typography', () => {
  assert.equal(normalizeText('“Built” the  ‘new’ system — fast…'), '"Built" the \'new\' system - fast...');
  assert.equal(needsUnicodeFont('Olajide Adewale café'), false);
  assert.equal(needsUnicodeFont('Ọlájídé Adéwálé'), true);
  assert.equal(toWinAnsi('Ọlájídé'), 'Olájídé');
});

function fontNames(doc: PDFDocument): string[] {
  const fonts = doc.getPage(0).node.Resources()!.lookup(PDFName.of('Font')) as unknown as { entries(): [unknown, unknown][] };
  return fonts.entries().map(([, ref]) => String((doc.context.lookup(ref as never) as unknown as { get(n: PDFName): unknown }).get(PDFName.of('BaseFont'))));
}

async function load(bytes: Uint8Array) {
  assert.equal(new TextDecoder().decode(bytes.slice(0, 5)), '%PDF-');
  return PDFDocument.load(bytes);
}

for (const [paper, size] of [['A4', [595.28, 841.89]], ['Letter', [612, 792]]] as const) {
  test(`valid PDF with selectable text on ${paper}`, async () => {
    const bytes = await generateResumePdf(sampleResume(), { paper });
    const doc = await load(bytes);
    const page = doc.getPage(0);
    assert.deepEqual([Math.round(page.getWidth() * 100) / 100, Math.round(page.getHeight() * 100) / 100], [...size]);
    assert.equal(doc.getTitle(), 'Jordan Lee - Resume');
    assert.equal(doc.getAuthor(), 'Jordan Lee');
    assert.match(doc.getKeywords() || '', /Terraform/);
    const resources = page.node.Resources()!;
    assert.ok(resources.lookup(PDFName.of('Font')), 'text is drawn with fonts');
    const xobjects = resources.lookup(PDFName.of('XObject')) as unknown as { entries(): [unknown, unknown][] } | undefined;
    const images = (xobjects?.entries() ?? []).filter(([, ref]) =>
      String((doc.context.lookup(ref as never) as unknown as { dict?: { get(n: PDFName): unknown } }).dict?.get(PDFName.of('Subtype'))) === '/Image');
    assert.equal(images.length, 0, 'no images: nothing is rasterised');
    assert.ok(fontNames(doc).some(n => n.includes('Helvetica-Bold')), 'standard Helvetica fonts');
  });
}

test('long resumes flow onto more pages without losing content', async () => {
  const long = sampleResume();
  long.experience = Array.from({ length: 12 }, (_, i) => ({ ...long.experience[0], company: `Company ${i}`,
    bullets: Array.from({ length: 6 }, (_, j) => `Delivered improvement ${j} for team ${i} across 40 services with measurable results.`) }));
  const doc = await load(await generateResumePdf(long, { paper: 'Letter' }));
  assert.ok(doc.getPageCount() >= 3);
});

test('names outside WinAnsi are kept by embedding a Unicode font', async () => {
  const fonts = { regular: new Uint8Array(readFileSync(new URL('../../../public/fonts/dejavu/DejaVuSans.ttf', import.meta.url))),
    bold: new Uint8Array(readFileSync(new URL('../../../public/fonts/dejavu/DejaVuSans-Bold.ttf', import.meta.url))) };
  const data = { ...sampleResume(), fullName: 'Ọlájídé Adéwálé' };
  const bytes = await generateResumePdf(data, { unicodeFonts: fonts });
  const doc = await load(bytes);
  assert.equal(doc.getAuthor(), 'Ọlájídé Adéwálé');
  assert.ok(fontNames(doc).some(n => n.includes('DejaVuSans')), 'Unicode font embedded');
  const fallback = await load(await generateResumePdf(data));          // no Unicode font available
  assert.equal(fallback.getAuthor(), 'Olájídé Adéwálé');                 // only the letter Helvetica cannot draw is simplified
});

test('a space between bold and regular text survives (extractors read "Frontend: React", not "Frontend:React")', async () => {
  const { Layout } = await import('../pdfEngine');
  const { StandardFonts } = await import('pdf-lib');
  const doc = await PDFDocument.create();
  const fonts = { regular: await doc.embedFont(StandardFonts.Helvetica), bold: await doc.embedFont(StandardFonts.HelveticaBold),
    italic: await doc.embedFont(StandardFonts.HelveticaOblique), unicode: false };
  const layout = new Layout(doc, fonts, 'A4');
  const [line] = layout.wrapSegments([{ text: 'Frontend: ', style: 'bold' }, { text: 'React, Tailwind' }], 10, 400);
  const runs = layout.runs(line);
  assert.deepEqual(runs.map(r => r.text), ['Frontend: ', 'React, Tailwind']);
  assert.ok(layout.measure(runs[0].text, 10, 'bold') > layout.measure('Frontend:', 10, 'bold'), 'the trailing space has width');
});

test('A4 and US Letter pages use the exact point sizes, and the header type sizes match the spec', async () => {
  const { TYPE } = await import('../types');
  assert.deepEqual({ name: TYPE.name, headline: TYPE.headline, contact: TYPE.contact, heading: TYPE.heading }, { name: 17, headline: 10, contact: 9.5, heading: 11 });
  for (const [paper, size] of [['A4', [595.28, 841.89]], ['Letter', [612, 792]]] as const) {
    const doc = await PDFDocument.load(await generateResumePdf(sampleResume(), { paper }));
    const { width, height } = doc.getPage(0).getSize();
    assert.deepEqual([Math.round(width * 100) / 100, Math.round(height * 100) / 100], [...size], paper);
  }
});

test('a header that wraps onto two lines moves to the next page as a whole', async () => {
  const { Layout } = await import('../pdfEngine');
  const { StandardFonts } = await import('pdf-lib');
  const doc = await PDFDocument.create();
  const fonts = { regular: await doc.embedFont(StandardFonts.Helvetica), bold: await doc.embedFont(StandardFonts.HelveticaBold),
    italic: await doc.embedFont(StandardFonts.HelveticaOblique), unicode: false };
  const L = new Layout(doc, fonts, 'A4');
  const header = [{ text: 'Principal Site Reliability Engineer, Platform Infrastructure | A Very Long Company Name Limited · Lagos, Nigeria', style: 'bold' as const }];
  const lineH = 10.2 * 1.32;
  assert.ok(L.measureLeftRight(header, 'Jan 2022 – Present') > lineH * 1.5, 'the header really wraps');
  L.y = 46 + lineH * 1.5;            // room for one line only above the bottom margin
  L.drawLeftRight(header, 'Jan 2022 – Present');
  assert.equal(doc.getPageCount(), 2, 'moved to a new page');
  const top = 841.89 - 46;
  assert.ok(Math.abs(L.y - (top - 2 * lineH)) < 0.01, 'both lines are on the new page');
});
