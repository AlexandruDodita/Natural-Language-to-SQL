/**
 * A deliberately small SQL pretty-printer.
 *
 * The workbench Format button is a readability aid, not a parser: it breaks the
 * major clauses onto their own lines and indents what follows. Anything it does
 * not recognise is left exactly as written, and the query that gets executed is
 * re-parsed server side by `validator.py` regardless.
 */
const MAJOR = [
  'WITH', 'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT',
  'OFFSET', 'UNION ALL', 'UNION', 'INTERSECT', 'EXCEPT',
];
const JOINS = [
  'LEFT OUTER JOIN', 'RIGHT OUTER JOIN', 'FULL OUTER JOIN', 'LEFT JOIN',
  'RIGHT JOIN', 'INNER JOIN', 'CROSS JOIN', 'FULL JOIN', 'JOIN',
];

export function formatSql(sql: string): string {
  let out = sql.replace(/\s+/g, ' ').trim();

  for (const kw of [...MAJOR, ...JOINS]) {
    const re = new RegExp(`\\s+${kw.replace(/ /g, '\\s+')}\\s+`, 'gi');
    out = out.replace(re, `\n${kw} `);
  }
  out = out.replace(/\s+ON\s+/gi, ' ON ');
  out = out.replace(/,\s*/g, ',\n  ');
  // A comma inside a function call should not have split the line.
  out = out
    .split('\n')
    .reduce<string[]>((acc, line) => {
      const prev = acc[acc.length - 1];
      const opens = (s: string) => (s.match(/\(/g) || []).length - (s.match(/\)/g) || []).length;
      if (prev !== undefined && opens(acc.join('\n')) > 0) {
        acc[acc.length - 1] = `${prev} ${line.trim()}`;
        return acc;
      }
      acc.push(line);
      return acc;
    }, [])
    .join('\n');

  return out
    .split('\n')
    .map(l => l.trimEnd())
    .filter((l, i, a) => l.trim() !== '' || i === a.length - 1)
    .join('\n')
    .trim();
}

export function toCsv(columns: string[], rows: unknown[][]): string {
  const cell = (v: unknown) => {
    if (v === null || v === undefined) return '';
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(cell).join(','), ...rows.map(r => r.map(cell).join(','))].join('\n');
}

export function download(filename: string, content: string | Blob, mime = 'text/plain') {
  const blob = typeof content === 'string' ? new Blob([content], { type: mime }) : content;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
