// On-device redaction of German official letters. Pure JS, no deps.
// Over-redacting is preferred to leaking. Deadline dates, amounts and the authority name are kept.

const W = 'A-Za-zÄÖÜäöüßé';
const NAMEWORD = `[A-ZÄÖÜ][a-zäöüßé]+(?:-[A-ZÄÖÜ][a-zäöüßé]+)*`;
const NAME2 = `${NAMEWORD}(?:[ \\t]+${NAMEWORD}){1,2}`;
const NAME13 = `${NAMEWORD}(?:[ \\t]+${NAMEWORD}){0,2}`;
const SUFFIX = '(?:[sS]tra(?:ß|ss)e|[sS]tr\\.|[wW]eg|[pP]latz|[aA]llee|[gG]asse|[rR]ing|[dD]amm|[uU]fer|[sS]teig|[pP]fad|[hH]of)';
const STREET = `(?:[A-ZÄÖÜ][\\wäöüß.\\-]*[ \\t]+)?[\\wäöüß.\\-]*?${SUFFIX}[ \\t]*\\d+(?:[ \\t]?[a-z])?(?:-\\d+)?`;
const PLZCITY = `\\b\\d{5}[ \\t]+(?!Euro|EUR|Cent)[A-ZÄÖÜ][\\wäöüß\\-]+`;
const AUTHORITY = /Ausländerbehörde|Stadt\s+[A-ZÄÖÜ]|Jobcenter|Finanzamt|Familienkasse|Behörde|Amt\s+für|Landratsamt|Bundesagentur|Agentur\s+für\s+Arbeit|Bundesamt|Rathaus|Rundfunk|Kita|Schule/;
const PH_RE = /\[[A-Z]+(?:_[A-Z]+)*(?:_\d+)?\]/g;
const PLACEHOLDER_ONLY = /^\[[A-Z]+(?:_[A-Z]+)*(?:_\d+)?\]$/;

const ID_KEYS =
  '(?:Aktenzeichen|Az\\.?|Kundennummer|Kunden-Nr\\.?|BG-Nummer|Bedarfsgemeinschaftsnummer|Steuer-ID|Steuer-Identifikationsnummer|Steuernummer|Ihr Zeichen|Ihre Zeichen|Unser Zeichen|Geschäftszeichen)';
const ID_VALUE = '[\\wÄÖÜäöüß/.\\-]*\\d[\\wÄÖÜäöüß/.\\-]*(?:[ ]\\d{3,}){0,3}';

const IBAN = /\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b/g;
const EMAIL = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;
const PHONE = /(?:\+|\b00)\d[\d ()/\-]{5,}\d|\b0\d{2,5}[ /\-]?\d[\d ()/\-]{3,}\d/g;

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function redact(text) {
  const mapping = {};
  const byValue = {};
  const counters = {};

  function ph(kind, value) {
    const key = kind + '|' + value;
    if (byValue[key]) return byValue[key];
    counters[kind] = (counters[kind] || 0) + 1;
    const p = counters[kind] === 1 ? `[${kind}]` : `[${kind}_${counters[kind]}]`;
    byValue[key] = p;
    mapping[p] = value;
    return p;
  }

  // split trailing punctuation off a captured value so it stays in the text
  function trimmed(kind, raw) {
    const m = raw.match(/^(.*?)([.,;:\-/]*)$/s);
    return ph(kind, m[1]) + m[2];
  }

  let out = text;

  // 1. IBAN, email, keyed IDs, birthdates, phones
  out = out.replace(IBAN, (m) => ph('IBAN', m));
  out = out.replace(EMAIL, (m) => ph('EMAIL', m));
  out = out.replace(new RegExp(`\\b(${ID_KEYS})(?=[\\s:.])([ \\t]*:?[ \\t]*)(${ID_VALUE})`, 'g'), (_, k, sep, v) => k + sep + trimmed('FILE_NO', v));
  out = out.replace(
    /\b(geb\.(?:[ \t]*am)?|geboren(?:[ \t]+am)?|Geburtsdatum:?)([ \t]*)(\d{1,2}\.\d{1,2}\.\d{2,4}(?:[ \t]+in[ \t]+[A-ZÄÖÜ][\wäöüß\-]+)?)/g,
    (_, k, sep, v) => k + sep + ph('BIRTHDATE', v),
  );
  out = out.replace(PHONE, (m) => {
    const digits = m.replace(/\D/g, '');
    return digits.length >= 7 ? ph('PHONE', m) : m;
  });

  // 2. Names after Herr/Frau and in salutation
  const titled = `((?:(?:Dr|Prof)\\.[ \\t]*)*)(${NAME13})`;
  out = out.replace(new RegExp(`\\b(Herrn?|Frau|Familie)[ \\t]+${titled}`, 'g'), (_, h, t, n) => `${h} ${t}${ph('NAME', n)}`);
  out = out.replace(
    new RegExp(`(Sehr geehrte[rsn]?[ \\t]+)(?!Damen|Herr|Frau|Familie)${titled}`, 'g'),
    (_, s, t, n) => `${s}${t}${ph('NAME', n)}`,
  );

  // 3. Recipient address block, line by line; skip the authority's own address
  const lines = out.split('\n');
  let inAuthority = false;
  const streetRe = new RegExp(STREET);
  const streetCity = new RegExp(`${STREET}(?:[ \\t]*,?[ \\t·]*${PLZCITY})?`, 'g');
  const plzRe = new RegExp(PLZCITY, 'g');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const hasStreet = streetRe.test(line);
    const hasPlz = new RegExp(PLZCITY).test(line);
    if (AUTHORITY.test(line)) {
      inAuthority = true;
      continue;
    }
    if (!hasStreet && !hasPlz) {
      if (line.trim() !== '' && !/@|tel|fax|www|\+?\d{3,}/i.test(line)) inAuthority = false;
      if (line.trim() === '') inAuthority = false;
      // bare recipient name line directly above a street line
      const nm = line.match(new RegExp(`^([ \\t]*)(${NAME2})[ \\t]*$`));
      if (nm && !PLACEHOLDER_ONLY.test(line.trim())) {
        const next = lines.slice(i + 1).find((l) => l.trim() !== '');
        if (next && new RegExp(STREET).test(next) && !AUTHORITY.test(next)) lines[i] = nm[1] + ph('NAME', nm[2]);
      }
      continue;
    }
    const startsAddr = new RegExp(`^[ \\t]*(?:${STREET}|\\d{5}[ \\t])`).test(line);
    if (inAuthority && startsAddr) continue;
    inAuthority = false;
    let l = line;
    const lead = l.match(new RegExp(`^([ \\t]*)(${NAME2})([ \\t]*,)`));
    if (lead) l = lead[1] + ph('NAME', lead[2]) + lead[3] + l.slice(lead[0].length);
    l = l.replace(streetCity, (m) => ph('ADDRESS', m)).replace(plzRe, (m) => ph('ADDRESS', m));
    lines[i] = l;
  }
  out = lines.join('\n');

  // 4. Remaining occurrences of redacted values (and single name parts) elsewhere in the text
  const nameParts = [];
  for (const [p, v] of Object.entries(mapping)) {
    if (p.startsWith('[NAME')) for (const part of v.split(/[ \t]+/)) if (part.length >= 3 && /^[A-ZÄÖÜ]/.test(part)) nameParts.push(part);
  }
  for (const part of nameParts) ph('NAME', part);
  const entries = Object.entries(mapping)
    .filter(([, v]) => v.length >= 3)
    .sort((a, b) => b[1].length - a[1].length);
  for (const [p, v] of entries) {
    out = out.replace(new RegExp(`(?<![\\wäöüßÄÖÜ])${escapeRe(v)}(?![\\wäöüßÄÖÜ])`, 'g'), p);
  }

  const seen = new Set();
  const placeholders = [];
  for (const m of out.match(PH_RE) || []) {
    if (mapping[m] !== undefined && !seen.has(m)) {
      seen.add(m);
      placeholders.push(m);
    }
  }
  // drop unused mapping entries (e.g. name parts that never appear on their own)
  for (const p of Object.keys(mapping)) if (!seen.has(p)) delete mapping[p];

  return { text: out, placeholders, mapping };
}

export function fillPlaceholders(text, mapping) {
  return text.replace(PH_RE, (p) => (Object.prototype.hasOwnProperty.call(mapping, p) ? mapping[p] : p));
}

// Split into words, whitespace and placeholder tokens. tokens.map(t => t.text).join('') === text.
export function tokenize(text) {
  return text
    .split(/(\s+|\[[A-Z]+(?:_[A-Z]+)*(?:_\d+)?\])/)
    .filter((s) => s !== '')
    .map((s) => (PLACEHOLDER_ONLY.test(s) ? { text: s, placeholder: s } : { text: s }));
}
