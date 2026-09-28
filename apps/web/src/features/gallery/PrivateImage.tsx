import { useState } from 'react'
import type { AuthView } from '../../shared/api'
import type { Asset } from '../../shared/workspace-api'
import { usePrivateImageUrl } from '../../shared/usePrivateImageUrl'

/** Own one decoded object URL and release it on route/session changes. No persistent pixel cache. */
export function PrivateImage({ asset, auth }: { asset: Asset; auth: AuthView }) {
  const [version, setVersion] = useState(0)
  const { url, error } = usePrivateImageUrl(asset, auth, version)
  return <div className="private-image">{url ? <img data-testid="private-image" src={url} alt="Сохранённое приватное изображение"
    width={asset.width} height={asset.height} /> : error ? <div className="field-error" role="alert">{error}
      <button onClick={() => setVersion(v => v + 1)}>Повторить предпросмотр</button></div> : <p role="status">Получаем изображение…</p>}</div>
}
