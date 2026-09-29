import { apiRequest, ApiError, chatProblem as baseChatProblem, type AuthView, type MessageView } from '../../shared/api'
import { uploadContent, type Asset, type Upload } from '../../shared/workspace-api'
import { ImageProblem, PreflightProblem, markChatOperationStarted, forgetChatOperations, persistedChatWarning } from './useChatPreflight'
export { pendingChatNotice, reserveChatOperation, forgetChatOperations,
  forgetUnstartedOperations } from './useChatPreflight'

export const CHAT_IMAGE_ACCEPT = 'image/png,image/jpeg,image/webp'
export type ImageType = 'image/png' | 'image/jpeg' | 'image/webp'
export type ChatAttachmentDraft = {
  id: string
  operationId: string
  file: File
  url: string
  uploadId?: string
  assetId?: string
}
export type Prepared = { bytes: ArrayBuffer; type: ImageType; width: number; height: number; hash: string }

function typeOf(bytes: Uint8Array): ImageType | null {
  if (bytes.length >= 8 && [137, 80, 78, 71, 13, 10, 26, 10].every((n, i) => bytes[i] === n)) return 'image/png'
  if (bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return 'image/jpeg'
  if (bytes.length >= 12 && String.fromCharCode(...bytes.slice(0, 4)) === 'RIFF'
    && String.fromCharCode(...bytes.slice(8, 12)) === 'WEBP') return 'image/webp'
  return null
}

export async function prepareChatImage(file: File, maximum: number): Promise<Prepared> {
  if (!Number.isSafeInteger(maximum) || maximum < 1 || file.size < 1) throw new ImageProblem('type')
  if (file.size > maximum) throw new ImageProblem('size')
  const bytes = await file.arrayBuffer()
  const type = typeOf(new Uint8Array(bytes))
  if (!type || file.type !== type) throw new ImageProblem('type')
  const url = URL.createObjectURL(new Blob([bytes], { type }))
  let width = 0, height = 0
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    width = image.naturalWidth; height = image.naturalHeight
    if (!width || !height || width > 8192 || height > 8192 || width * height > 16_777_216)
      throw new ImageProblem('decode')
  } catch { throw new ImageProblem('decode') }
  finally { URL.revokeObjectURL(url) }
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))
  const hash = Array.from(digest).map(n => n.toString(16).padStart(2, '0')).join('')
  return { bytes, type, width, height, hash }
}

export function chatImageProblem(reason: unknown): string {
  if (reason instanceof ImageProblem) {
    if (reason.code === 'size') return 'Изображение слишком большое.'
    if (reason.code === 'uncertain') return 'Состояние загрузки неизвестно. Выберите тот же файл для проверки; без него отправка невозможна.'
    if (reason.code === 'storage') return 'Браузер не сохранил состояние загрузки. Разрешите хранилище и повторите выбор файла.'
    if (reason.code === 'other_tab') return 'Загрузка изображений уже открыта в другой вкладке. Завершите её там или закройте вкладку.'
    if (reason.code === 'locks') return 'Этот браузер не поддерживает безопасное восстановление загрузки изображений.'
    if (reason.code === 'terminal') return 'Предыдущая загрузка завершилась без изображения. Удалите вложение и выберите файл заново.'
    return reason.code === 'decode' ? 'Изображение повреждено или превышает допустимые размеры.' : 'Поддерживаются PNG, JPEG и WebP.'
  }
  if (reason instanceof ApiError) {
    if (['upload_too_large', 'canonical_image_too_large', 'image_too_large'].includes(reason.code))
      return 'Изображение слишком большое.'
    if (reason.code === 'upload_not_allowed') return 'План аккаунта не разрешает загрузку изображений. Администратор должен настроить лимит.'
    if (reason.code === 'upload_busy') return 'Изображение ещё обрабатывается. Черновик сохранён.'
    if (reason.code === 'plan_unconfigured') return 'Администратор ещё не настроил лимиты загрузки изображений для аккаунта.'
    if (reason.code === 'plan_restricted') return 'Ваш план пока не разрешает загрузку изображений.'
    if (['invalid_image', 'upload_content_mismatch', 'content_type_rejected'].includes(reason.code))
      return 'Неподдерживаемое или повреждённое изображение.'
    if (reason.code === 'storage_quota_exceeded') return 'Недостаточно места для изображения.'
  }
  return 'Не удалось сохранить изображение. Черновик сохранён.'
}

export function chatProblem(reason: unknown): string {
  if (reason instanceof PreflightProblem) return reason.message
  if (reason instanceof ApiError) {
    if (reason.code === 'model_vision_unsupported') return 'Выбранная модель больше не принимает изображения.'
    if (reason.code === 'attachment_not_found') return 'Изображение недоступно этому аккаунту. Прикрепите его заново.'
    if (['image_too_large', 'image_context_too_large'].includes(reason.code))
      return 'Изображения превышают допустимый размер запроса.'
    if (['attachment_unavailable', 'attachment_integrity_error'].includes(reason.code))
      return 'Сервер не смог проверить изображение. Черновик сохранён.'
  }
  return baseChatProblem(reason)
}

export async function lastChatWarning(messages: MessageView[], signal?: AbortSignal) {
  const last = [...messages].reverse().find(message => message.role === 'assistant')
  return last && ['error', 'interrupted', 'stopped'].includes(last.state)
    ? persistedChatWarning(last.request_id, signal) : ''
}

const uploadPath = '/api/v1/media/uploads'
async function begin(draft: ChatAttachmentDraft, image: Prepared, auth: AuthView): Promise<Upload> {
  const data = { operation_id: draft.operationId, content_type: image.type,
    byte_size: image.bytes.byteLength, sha256: image.hash, width: image.width, height: image.height }
  const create = () => apiRequest<Upload>(uploadPath, { method: 'POST', csrf: auth.csrf_token,
    data, timeoutMs: 20000 })
  try { return await create() }
  catch (reason) {
    if (reason instanceof ApiError && reason.status < 500) throw reason
    try { return await create() } catch { throw new ImageProblem('uncertain') }
  }
}

export async function uploadChatImage(draft: ChatAttachmentDraft, auth: AuthView, maximum: number): Promise<Asset> {
  const image = await prepareChatImage(draft.file, maximum)
  await markChatOperationStarted(auth.account.id, draft.operationId, image)
  let upload: Upload
  if (draft.uploadId) upload = await apiRequest<Upload>(`${uploadPath}/${draft.uploadId}`)
  else {
    upload = await begin(draft, image, auth)
    draft.uploadId = upload.id
  }
  if (upload.status === 'pending' || upload.status === 'validating') {
    try { upload = await uploadContent(upload.id, image.bytes, auth) }
    catch (reason) {
      if (reason instanceof ApiError && reason.status < 500) throw reason
      try { upload = await apiRequest<Upload>(`${uploadPath}/${draft.uploadId}`) }
      catch { throw new ImageProblem('uncertain') }
    }
  }
  if (upload.status === 'storing') {
    try { upload = await apiRequest<Upload>(`${uploadPath}/${draft.uploadId}/complete`, {
      method: 'POST', csrf: auth.csrf_token, data: {}, timeoutMs: 15000,
    }) } catch {
      try { upload = await uploadContent(upload.id, image.bytes, auth) }
      catch {
        try { upload = await apiRequest<Upload>(`${uploadPath}/${draft.uploadId}`) }
        catch { throw new ImageProblem('uncertain') }
      }
    }
  }
  if (['rejected', 'expired', 'cancelled'].includes(upload.status)) {
    await forgetChatOperations(auth.account.id, [draft]); throw new ImageProblem('terminal')
  }
  if (upload.status !== 'ready' || !upload.asset_id) throw new ImageProblem('uncertain')
  draft.assetId = upload.asset_id
  const asset = await apiRequest<Asset>(`/api/v1/media/assets/${upload.asset_id}`)
  if (asset.byte_size > maximum) throw new ImageProblem('size')
  return asset
}

export async function resolveChatAttachments(drafts: ChatAttachmentDraft[], auth: AuthView,
  maximum: number): Promise<string[]> {
  const ids: string[] = []
  for (const draft of drafts) ids.push((await uploadChatImage(draft, auth, maximum)).id)
  return ids
}
