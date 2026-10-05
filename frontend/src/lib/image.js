const MAX_SIDE = 2000
const QUALITY = 0.85

async function decode(file) {
  if (typeof createImageBitmap === 'function') {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch {
      /* fall through to <img> */
    }
  }
  const url = URL.createObjectURL(file)
  try {
    return await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = url
    })
  } finally {
    URL.revokeObjectURL(url)
  }
}

// Images -> JPEG File with longest side <= 2000px. Everything else (PDF, undecodable) unchanged.
export async function downscaleImage(file) {
  if (!file || !file.type || !file.type.startsWith('image/')) return file
  try {
    const img = await decode(file)
    const w = img.naturalWidth || img.width
    const h = img.naturalHeight || img.height
    if (!w || !h) return file
    const scale = Math.min(1, MAX_SIDE / Math.max(w, h))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(w * scale)
    canvas.height = Math.round(h * scale)
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    if (img.close) img.close()
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
    if (!blob) return file
    const base = (file.name || 'letter').replace(/\.[^.]+$/, '')
    return new File([blob], base + '.jpg', { type: 'image/jpeg' })
  } catch {
    return file
  }
}
