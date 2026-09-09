import { useEffect, useState } from 'react'
import type { AuthView } from '../../shared/api'
import { type Asset, imageBlob, problem } from '../../shared/workspace-api'

/** Own one object URL and release it on route/session changes. No persistent pixel cache. */
export function PrivateImage({ asset, auth }: { asset: Asset; auth: AuthView }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let ownedUrl = ''
    setUrl(''); setError('')
    imageBlob(asset, auth, controller.signal).then(blob => {
      if (controller.signal.aborted) return
      ownedUrl = URL.createObjectURL(blob); setUrl(ownedUrl)
    }).catch(reason => { if (!controller.signal.aborted) setError(problem(reason)) })
    return () => { controller.abort(); if (ownedUrl) URL.revokeObjectURL(ownedUrl) }
  }, [asset.id, asset.sha256, asset.byte_size, auth.account.id, auth.csrf_token, version])
  return <div className="private-image">{url ? <img data-testid="private-image" src={url} alt="Сохранённое приватное изображение"
    width={asset.width} height={asset.height} /> : error ? <div className="field-error" role="alert">{error}
      <button onClick={() => setVersion(v => v + 1)}>Повторить предпросмотр</button></div> : <p role="status">Получаем изображение…</p>}</div>
}
