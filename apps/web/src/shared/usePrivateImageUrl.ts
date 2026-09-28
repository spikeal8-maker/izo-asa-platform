import { useEffect, useState } from 'react'
import type { AuthView } from './api'
import { imageBlob, problem, type Asset } from './workspace-api'

/** One private object URL per mount. The caller never receives a signed Media ticket. */
export function usePrivateImageUrl(asset: Pick<Asset, 'id' | 'sha256' | 'byte_size' | 'width' | 'height'>,
  auth: AuthView, retryVersion = 0) {
  const [url, setUrl] = useState('')
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
    }).catch(reason => {
      if (controller.signal.aborted) return
      if (ownedUrl) { URL.revokeObjectURL(ownedUrl); ownedUrl = '' }
      setError(problem(reason))
    })
    return () => { controller.abort(); if (ownedUrl) URL.revokeObjectURL(ownedUrl) }
  }, [asset.id, asset.sha256, asset.byte_size, asset.width, asset.height, auth.account.id, auth.csrf_token, version, retryVersion])
  return { url, error, retry: () => setVersion(value => value + 1) }
}
