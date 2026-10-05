import { describe, it, expect } from 'vitest'
import { sanitizeMessage, refreshDays, daysUntil, loadHistory, saveHistory } from '../src/lib/history.js'

function memoryStorage() {
  const data = {}
  return { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v }, removeItem: (k) => { delete data[k] } }
}

describe('sanitizeMessage', () => {
  it('never keeps photos', () => {
    const m = sanitizeMessage({ id: 1, from: 'me', kind: 'photo', url: 'blob:x', name: 'IMG_1.jpg' })
    expect(JSON.stringify(m)).not.toContain('blob:')
    expect(JSON.stringify(m)).not.toContain('IMG_1')
  })

  it('drops the originals of words the user hid', () => {
    const m = sanitizeMessage({
      id: 2, from: 'bot', kind: 'review', confirmed: true,
      tokens: [{ text: '[HIDDEN]', hidden: true, original: 'Mustermann' }, { text: '[NAME]', hidden: true, placeholder: '[NAME]' }],
    })
    expect(JSON.stringify(m)).not.toContain('Mustermann')
    expect(m.tokens[1].placeholder).toBe('[NAME]')
  })

  it('stores the draft with placeholders, not the filled-in names', () => {
    const m = sanitizeMessage({ id: 3, from: 'bot', kind: 'draft', text: 'Gruß, Max Mustermann', raw: 'Gruß, [NAME]' })
    expect(m.text).toBe('Gruß, [NAME]')
    expect(JSON.stringify(m)).not.toContain('Mustermann')
  })

  it('skips transient messages', () => {
    for (const kind of ['typing', 'actions', 'error']) expect(sanitizeMessage({ id: 4, from: 'bot', kind })).toBeNull()
  })
})

describe('refreshDays', () => {
  const analysis = {
    light: 'yellow',
    deadline: { date: '2026-10-30', daysLeft: 25 },
    otherDates: [{ date: '2026-11-15', daysLeft: 41 }],
  }

  it('recounts days against today', () => {
    const a = refreshDays(analysis, new Date(2026, 9, 20))
    expect(a.deadline.daysLeft).toBe(10)
    expect(a.otherDates[0].daysLeft).toBe(26)
  })

  it('escalates a stale light to red within 14 days', () => {
    expect(refreshDays(analysis, new Date(2026, 9, 20)).light).toBe('red')
    expect(refreshDays(analysis, new Date(2026, 9, 5)).light).toBe('yellow')
  })

  it('handles overdue dates', () => {
    expect(daysUntil('2026-10-13', new Date(2026, 9, 15))).toBe(-2)
  })
})

describe('storage', () => {
  it('round-trips and survives broken data', () => {
    const s = memoryStorage()
    saveHistory([{ id: 'a' }], s)
    expect(loadHistory(s)).toEqual([{ id: 'a' }])
    s.setItem('briefklar.history.v1', '{not json')
    expect(loadHistory(s)).toEqual([])
  })
})
