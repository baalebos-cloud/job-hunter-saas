/* eslint-disable react/prop-types -- the project does not use the prop-types package */
// Renders the small Markdown subset used by the legal documents (headings,
// paragraphs, bullet lists, tables, **bold**) as React elements. Nothing is
// injected as HTML, so text typed in the Legal console can never run as script.

function inline(text, keyBase) {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) => (
    part.startsWith('**') && part.endsWith('**') ? <strong key={`${keyBase}-${i}`}>{part.slice(2, -2)}</strong> : part));
}

const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());

export function parseBlocks(source) {
  const lines = String(source || '').replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    const heading = line.match(/^(#{1,3})\s+(.*)$/);
    if (heading) { blocks.push({ type: `h${heading[1].length}`, text: heading[2] }); i += 1; continue; }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, '')); i += 1; }
      blocks.push({ type: 'ul', items }); continue;
    }
    if (line.trim().startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(lines[i]); i += 1; }
      const body = rows.filter((_, n) => n !== 1 || !/^\s*\|?\s*:?-{2,}/.test(rows[1]));
      blocks.push({ type: 'table', head: cells(body[0]), rows: body.slice(1).map(cells) }); continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|\s*[-*]\s|\s*\|)/.test(lines[i])) { para.push(lines[i].trim()); i += 1; }
    blocks.push({ type: 'p', text: para.join(' ') });
  }
  return blocks;
}

export default function LegalText({ source, skipTitle = true }) {
  const blocks = parseBlocks(source).filter((b, n) => !(skipTitle && n === 0 && b.type === 'h1'));
  return (
    <div className="space-y-4 text-[15.5px] leading-7 text-slate-700">
      {blocks.map((b, n) => {
        if (b.type === 'h1') return <h1 key={n} className="text-3xl font-semibold text-slate-900">{b.text}</h1>;
        if (b.type === 'h2') return <h2 key={n} className="pt-4 text-xl font-semibold text-slate-900">{inline(b.text, n)}</h2>;
        if (b.type === 'h3') return <h3 key={n} className="pt-2 font-semibold text-slate-900">{inline(b.text, n)}</h3>;
        if (b.type === 'ul') return <ul key={n} className="list-disc pl-6 space-y-1.5">{b.items.map((t, k) => <li key={k}>{inline(t, `${n}-${k}`)}</li>)}</ul>;
        if (b.type === 'table') return (
          <div key={n} className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left"><tr>{b.head.map((h, k) => <th key={k} className="px-3 py-2 font-semibold text-slate-900">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-100">{b.rows.map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j} className="px-3 py-2 align-top">{inline(c, `${n}-${k}-${j}`)}</td>)}</tr>)}</tbody>
            </table>
          </div>);
        return <p key={n}>{inline(b.text, n)}</p>;
      })}
    </div>
  );
}
