// Letter history, kept only in this browser's localStorage.
// Saved: redacted text, the analysis and the chat messages. Never saved: photos and the
// placeholder → original mapping, so real names and addresses don't end up on disk.

const KEY = 'briefklar.history.v1'
const SAVED_KINDS = new Set(['text', 'photo', 'review', 'analysis', 'answer', 'draft', 'glossary', 'sources'])

export function loadHistory(storage = globalThis.localStorage) {
  try {
    const list = JSON.parse(storage?.getItem(KEY) || '[]')
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function saveHistory(list, storage = globalThis.localStorage) {
  try {
    storage?.setItem(KEY, JSON.stringify(list))
  } catch {
    // Storage full or disabled (private mode): history just isn't kept.
  }
}

export function clearHistoryStorage(storage = globalThis.localStorage) {
  try {
    storage?.removeItem(KEY)
  } catch {}
}

// Strips everything personal from a message before it is written to storage.
export function sanitizeMessage(m) {
  if (!SAVED_KINDS.has(m.kind)) return null
  if (m.kind === 'photo') return { id: m.id, from: 'me', kind: 'text', text: '📷 Photo (not saved)' }
  if (m.kind === 'review') {
    // `original` holds words the user chose to hide; drop it. Visible text is what was sent.
    return { ...m, tokens: m.tokens.map(({ original, ...t }) => t) }
  }
  if (m.kind === 'draft') {
    // The displayed draft has real names filled in; store the placeholder version.
    const { raw, ...rest } = m
    return { ...rest, text: raw ?? m.text }
  }
  return { ...m }
}

export function daysUntil(iso, today = new Date()) {
  const [y, mo, d] = String(iso).split('-').map(Number)
  if (!y) return null
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((Date.UTC(y, mo - 1, d) - start) / 86400000)
}

// Re-counts days left against today, so an old letter opened later shows the right countdown.
export function refreshDays(analysis, today = new Date()) {
  if (!analysis) return analysis
  const fix = (item) => (item ? { ...item, daysLeft: daysUntil(item.date, today) ?? item.daysLeft } : item)
  const deadline = fix(analysis.deadline)
  // Mirrors the server rule (≤ 14 days or overdue → red), but only ever escalates a stale light.
  const escalate = deadline && deadline.daysLeft <= 14 && analysis.light !== 'red'
  return {
    ...analysis,
    deadline,
    otherDates: (analysis.otherDates || []).map(fix),
    ...(escalate ? { light: 'red', lightReason: `Deadline in ${deadline.daysLeft} days (≤ 14 days)` } : {}),
  }
}
