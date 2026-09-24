import { apiBinaryRequest, apiRequest, ApiError, type AuthView } from '../../shared/api'
import type { Asset } from '../../shared/workspace-api'

export const CHAT_IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,image/gif'

type ImageType = 'image/png' | 'image/jpeg' | 'image/webp' | 'image/gif'
type PreparedImage = {
  bytes: ArrayBuffer
  contentType: ImageType
  width: number
  height: number
  sha256: string
}

class ChatImageError extends Error {
  constructor(public code: 'unsupported' | 'too_large' | 'decode') {
    super(code)
  }
}

function actualType(bytes: Uint8Array): ImageType | null {
  if (bytes.length >= 8
      && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47
      && bytes[4] === 0x0d && bytes[5] === 0x0a && bytes[6] === 0x1a && bytes[7] === 0x0a)
    return 'image/png'
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff)
    return 'image/jpeg'
  if (bytes.length >= 6) {
    const header = String.fromCharCode(...bytes.slice(0, 6))
    if (header === 'GIF87a' || header === 'GIF89a') return 'image/gif'
  }
  if (bytes.length >= 12
      && String.fromCharCode(...bytes.slice(0, 4)) === 'RIFF'
      && String.fromCharCode(...bytes.slice(8, 12)) === 'WEBP')
    return 'image/webp'
  return null
}

async function dimensions(bytes: ArrayBuffer, contentType: ImageType) {
  const url = URL.createObjectURL(new Blob([bytes], { type: contentType }))
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    if (!image.naturalWidth || !image.naturalHeight) throw new ChatImageError('decode')
    return { width: image.naturalWidth, height: image.naturalHeight }
  } catch (reason) {
    if (reason instanceof ChatImageError) throw reason
    throw new ChatImageError('decode')
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function prepareChatImage(file: File, maximum: number): Promise<PreparedImage> {
  if (!Number.isSafeInteger(maximum) || maximum < 1 || file.size < 1)
    throw new ChatImageError('unsupported')
  if (file.size > maximum) throw new ChatImageError('too_large')
  const bytes = await file.arrayBuffer()
  const contentType = actualType(new Uint8Array(bytes))
  if (!contentType) throw new ChatImageError('unsupported')
  const size = await dimensions(bytes, contentType)
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))
  const sha256 = Array.from(digest).map(value => value.toString(16).padStart(2, '0')).join('')
  return { bytes, contentType, ...size, sha256 }
}

export function chatImageProblem(reason: unknown): string {
  if (reason instanceof ChatImageError) {
    if (reason.code === 'too_large') return 'Файл слишком большой.'
    if (reason.code === 'decode') return 'Неподдерживаемый формат или повреждённое изображение.'
    return 'Неподдерживаемый формат.'
  }
  if (reason instanceof ApiError) {
    if (['upload_too_large', 'canonical_image_too_large', 'request_too_large', 'image_too_large'].includes(reason.code))
      return 'Файл слишком большой.'
    if (['invalid_image', 'upload_content_mismatch', 'content_type_rejected'].includes(reason.code))
      return 'Неподдерживаемый формат или повреждённое изображение.'
  }
  return 'Не удалось сохранить изображение.'
}

export async function uploadChatImage(
  file: File, auth: AuthView, maximum: number,
): Promise<Asset> {
  const prepared = await prepareChatImage(file, maximum)
  const intent = await apiRequest<{
    id: string
    status: string
    asset_id: string | null
  }>('/api/v1/media/uploads', {
    method: 'POST',
    csrf: auth.csrf_token,
    data: {
      operation_id: crypto.randomUUID(),
      content_type: prepared.contentType,
      byte_size: prepared.bytes.byteLength,
      sha256: prepared.sha256,
      width: prepared.width,
      height: prepared.height,
    },
    timeoutMs: 20000,
  })
  const stored = await apiBinaryRequest<{
    id: string
    status: string
    asset_id: string | null
  }>(`/api/v1/media/uploads/${intent.id}/content`, prepared.bytes, auth.csrf_token)
  if (stored.status !== 'ready' || !stored.asset_id) throw new Error('Media did not become ready')
  const asset = await apiRequest<Asset>(`/api/v1/media/assets/${stored.asset_id}`)
  if (asset.byte_size > maximum) throw new ChatImageError('too_large')
  return asset
}
