import { useEffect, useRef, useState } from 'react'
import type { AuthView } from '../../shared/api'
import { type Asset, imageBlob, problem } from '../../shared/workspace-api'

/** Own one decoded object URL and release it on route/session changes. No persistent pixel cache. */
export function PrivateImage({ asset, auth, onSettled }: {
  asset: Asset
  auth: AuthView
  onSettled?: () => void
}) {
  const [url, setUrl] = useState('')
  const settledRef = useRef(onSettled)
  settledRef.current = onSettled
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let ownedUrl = ''
    setUrl(''); setError('')
    imageBlob(asset, auth, controller.signal).then(async blob => {
      if (controller.signal.aborted) return
      ownedUrl = URL.createObjectURL(blob)
      const image = new Image()
      image.src = ownedUrl
      await image.decode()
      if (controller.signal.aborted) return
      if (image.naturalWidth !== asset.width || image.naturalHeight !== asset.height)
        throw new Error('Image dimensions mismatch')
      setUrl(ownedUrl)
      settledRef.current?.()
    }).catch(reason => {
      if (controller.signal.aborted) return
      if (ownedUrl) { URL.revokeObjectURL(ownedUrl); ownedUrl = '' }
      setError(problem(reason))
      settledRef.current?.()
    })
    return () => { controller.abort(); if (ownedUrl) URL.revokeObjectURL(ownedUrl) }
  }, [asset.id, asset.sha256, asset.byte_size, asset.width, asset.height, auth.account.id, auth.csrf_token, version])
  return <div className="private-image">{url ? <img data-testid="private-image" src={url} alt="Сохранённое приватное изображение"
    width={asset.width} height={asset.height} /> : error ? <div className="field-error" role="alert">{error}
      <button onClick={() => setVersion(v => v + 1)}>Повторить предпросмотр</button></div> : <p role="status">Получаем изображение…</p>}</div>
}
