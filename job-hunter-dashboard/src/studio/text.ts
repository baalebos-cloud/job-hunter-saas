// Text clean-up for the PDF. Standard PDF fonts (Helvetica) only cover the
// WinAnsi character set; anything outside it needs an embedded Unicode font,
// otherwise names such as "Ọlájídé" would be silently changed.

const REPLACEMENTS: Array<[RegExp, string]> = [
  [/[‘’‚′]/g, "'"], [/[“”„″]/g, '"'],
  [/[–—−]/g, '-'], [/[•●▪‣⁃]/g, '•'],
  [/…/g, '...'], [/[     ]/g, ' '], [/[​-‍﻿]/g, ''],
  [/\t/g, ' '], [/[\r\n]+/g, ' '],
];

// Unicode code points that WinAnsi (Windows-1252) can encode.
const WIN_ANSI_EXTRA = new Set([0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152,
  0x017D, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0x017E, 0x0178]);

export function isWinAnsi(char: string): boolean {
  const code = char.codePointAt(0) ?? 0;
  return (code >= 0x20 && code <= 0x7E) || (code >= 0xA0 && code <= 0xFF) || WIN_ANSI_EXTRA.has(code);
}

/** Normalise typography (smart quotes, dashes, odd spaces) without changing letters.
 *  `keepEdges` keeps leading/trailing spaces: the PDF layout relies on them between text runs. */
export function normalizeText(value: string, keepEdges = false): string {
  let text = String(value ?? '').normalize('NFC');
  for (const [pattern, replacement] of REPLACEMENTS) text = text.replace(pattern, replacement);
  text = text.replace(/ {2,}/g, ' ');
  return keepEdges ? text : text.trim();
}

export function needsUnicodeFont(value: string): boolean {
  return [...normalizeText(value)].some(ch => !isWinAnsi(ch));
}

/** Last resort when no Unicode font is available: strip accents, drop the rest. */
export function toWinAnsi(value: string, keepEdges = false): string {
  // Keep every character Helvetica can draw (á, é, ü...); only simplify the rest (Ọ -> O).
  return [...normalizeText(value, keepEdges)].map(ch => (isWinAnsi(ch) ? ch
    : [...ch.normalize('NFKD')].filter(isWinAnsi).join('').normalize('NFC'))).join('');
}
