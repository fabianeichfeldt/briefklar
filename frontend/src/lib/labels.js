export const OFFICES = {
  auslaenderbehoerde: 'Ausländerbehörde',
  jobcenter: 'Jobcenter',
  sozialamt: 'Sozialamt',
  buergeramt: 'Bürgeramt',
  kita_schule: 'Kita / School',
  finanzamt: 'Finanzamt',
  familienkasse: 'Familienkasse',
  rundfunkbeitrag: 'Rundfunkbeitrag',
  other: 'Other office',
}

export const LETTER_TYPES = {
  appointment_invitation: 'Appointment',
  document_request: 'Documents requested',
  decision: 'Decision',
  payment_request: 'Payment',
  reminder: 'Reminder',
  information: 'Information',
  other: 'Letter',
}

export const officeName = (code) => OFFICES[code] || code || 'Letter'

export const LANGS = [
  ['en', 'English'],
  ['uk', 'Українська'],
  ['ar', 'العربية'],
  ['tr', 'Türkçe'],
  ['fa', 'فارسی'],
  ['ro', 'Română'],
]
export const langName = (code) => (LANGS.find(([c]) => c === code) || [, 'English'])[1]
