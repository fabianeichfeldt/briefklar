// Thin client for the Briefklar API (see openapi.yaml). Never logs letter text.
const BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:4010'
const TIMEOUT_MS = 60000

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function request(path, init) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let res
  try {
    res = await fetch(BASE + path, { ...init, signal: controller.signal })
  } catch (e) {
    if (e && e.name === 'AbortError') {
      throw new ApiError(0, 'timeout', 'The request took too long.')
    }
    throw new ApiError(0, 'network', 'Could not reach the server.')
  } finally {
    clearTimeout(timer)
  }
  let body = null
  try {
    body = await res.json()
  } catch {
    body = null
  }
  if (!res.ok) {
    throw new ApiError(
      res.status,
      (body && body.code) || 'http_' + res.status,
      (body && body.message) || 'Request failed (' + res.status + ').'
    )
  }
  if (body === null) throw new ApiError(res.status, 'bad_response', 'Unexpected server response.')
  return body
}

export function extractText(file) {
  const form = new FormData()
  form.append('file', file, file.name || 'letter')
  return request('/extract', { method: 'POST', body: form })
}

export function analyzeLetter({ text, language = 'en', question = null }) {
  return request('/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language, question: question || null }),
  })
}
