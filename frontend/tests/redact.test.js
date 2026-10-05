import { describe, it, expect } from 'vitest';
import { redact, fillPlaceholders, tokenize } from '../src/lib/redact.js';
import { SAMPLE_LETTER_TEXT } from '../src/lib/sample.js';

const OPENAPI_TEXT = `Stadt Nürnberg · Ausländerbehörde
Max Mustermann, Musterstraße 1, 90402 Nürnberg
Aktenzeichen: AB-2026/48213-P
Sehr geehrter Herr Mustermann,
Ihr Aufenthaltstitel ist gültig bis 15.11.2026. Für die Verlängerung ist eine persönliche Vorsprache erforderlich.
Termin: 20.10.2026, 09:30 Uhr, Zimmer 2.14.
Eine Absage oder Verlegung ist bis zum 13.10.2026 möglich.
Mit freundlichen Grüßen
i. A. Schmidt
`;

for (const [name, text] of [['sample', SAMPLE_LETTER_TEXT], ['openapi', OPENAPI_TEXT]]) {
  describe(name, () => {
    const r = redact(text);
    it('removes personal data', () => {
      for (const s of ['Mustermann', 'Musterstraße', '90402', 'AB-2026/48213-P', 'DE00', '01.02.1990', 'Max']) {
        expect(r.text).not.toContain(s);
      }
    });
    it('keeps deadlines, amounts and authority', () => {
      for (const s of ['13.10.2026', '20.10.2026', '15.11.2026', 'Ausländerbehörde']) expect(r.text).toContain(s);
    });
    it('round-trips', () => {
      expect(fillPlaceholders(r.text, r.mapping)).toBe(text);
    });
    it('tokenize keeps placeholders whole and joins back', () => {
      const toks = tokenize(r.text);
      expect(toks.map((t) => t.text).join('')).toBe(r.text);
      for (const p of r.placeholders) expect(toks.some((t) => t.text === p && t.placeholder === p)).toBe(true);
      expect(toks.filter((t) => t.placeholder).every((t) => /^\[[A-Z_0-9]+\]$/.test(t.text))).toBe(true);
    });
    it('lists placeholders', () => {
      expect(r.placeholders).toContain('[NAME]');
      expect(r.placeholders).toContain('[FILE_NO]');
    });
  });
}

describe('sample specifics', () => {
  const r = redact(SAMPLE_LETTER_TEXT);
  it('redacts iban, birthdate, keeps amount and own address', () => {
    expect(r.text).toContain('[IBAN]');
    expect(r.text).toContain('[BIRTHDATE]');
    expect(r.text).toContain('100,00 EUR');
    expect(r.text).toContain('Beispielstraße 99');
  });
  it('same value reuses placeholder, distinct values are numbered', () => {
    expect((r.text.match(/\[FILE_NO\]/g) || []).length).toBe(1);
    const x = redact('Aktenzeichen: A-1\nKundennummer: 5555\nFrau Berta Beispiel und Herr Karl Klein, Frau Berta Beispiel');
    expect(x.text).toContain('[NAME_2]');
    expect(x.text.match(/\[NAME\]/g).length).toBe(2);
    expect(x.text).toContain('[FILE_NO_2]');
  });
  it('handles email and phone', () => {
    const x = redact('Kontakt: a.b@example.org, Tel. 0911 123456, +49 911 231-0');
    expect(x.text).not.toMatch(/example|123456|231/);
  });
});
