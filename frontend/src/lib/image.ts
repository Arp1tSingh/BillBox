const MAX_PAGES = 10
const MAX_FILE_MB = 10
const MAX_TOTAL_MB = 25
const LONG_SIDE = 1600
const QUALITY = 0.82

export interface PreparedPage {
  id: string
  file: File
  previewUrl: string | null
  isPdf: boolean
}

export class ImageError extends Error {}

function makeId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function validateSizes(files: File[]): void {
  const total = files.reduce((sum, file) => sum + file.size, 0)
  if (files.some((file) => file.size > MAX_FILE_MB * 1024 * 1024)) {
    throw new ImageError(`Each page must be under ${MAX_FILE_MB} MB.`)
  }
  if (total > MAX_TOTAL_MB * 1024 * 1024) {
    throw new ImageError(`Keep the whole bill under ${MAX_TOTAL_MB} MB.`)
  }
}

async function compressImage(file: File): Promise<File> {
  if (file.type === 'application/pdf') return file
  if (!file.type.startsWith('image/')) {
    throw new ImageError('Use JPEG, PNG, WebP images or a PDF.')
  }

  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    throw new ImageError('That image could not be read.')
  }

  const scale = Math.min(1, LONG_SIDE / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) {
    bitmap.close()
    throw new ImageError('This browser cannot prepare images.')
  }
  context.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', QUALITY),
  )
  if (!blob) throw new ImageError('That image could not be prepared.')
  const name = file.name.replace(/\.[^.]+$/, '') || 'page'
  return new File([blob], `${name}.jpg`, { type: 'image/jpeg', lastModified: Date.now() })
}

export async function preparePages(incoming: File[], existingCount = 0): Promise<PreparedPage[]> {
  if (existingCount + incoming.length > MAX_PAGES) {
    throw new ImageError(`Bills can have at most ${MAX_PAGES} pages.`)
  }
  validateSizes(incoming)

  return Promise.all(
    incoming.map(async (file) => {
      const isPdf = file.type === 'application/pdf'
      const prepared = await compressImage(file)
      return {
        id: makeId(),
        file: prepared,
        previewUrl: isPdf ? null : URL.createObjectURL(prepared),
        isPdf,
      }
    }),
  )
}

export function releasePages(pages: PreparedPage[]): void {
  for (const page of pages) {
    if (page.previewUrl) URL.revokeObjectURL(page.previewUrl)
  }
}

export function totalBytes(pages: PreparedPage[]): number {
  return pages.reduce((sum, page) => sum + page.file.size, 0)
}
