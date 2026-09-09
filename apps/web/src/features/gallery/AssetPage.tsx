import { useEffect, useRef, useState } from 'react'
import { Link } from '../../shell/router'
import { Icon } from '../../shared/ui/Icon'
import type { AuthView } from '../../shared/api'
import { WorkspaceGate, ResourceState, useResource } from '../../shared/workspace'
import { type Asset, isId, imageBlob, problem } from '../../shared/workspace-api'
import { PrivateImage } from './PrivateImage'
import './gallery.css'

type DownloadResource = { controller: AbortController; url: string; timer?: ReturnType<typeof setTimeout> }
function release(resource: DownloadResource | null) {
  if (!resource) return
  resource.controller.abort()
  clearTimeout(resource.timer)
  if (resource.url) URL.revokeObjectURL(resource.url)
}
function Work({ id, auth }: { id: string; auth: AuthView }) {
  const { data: asset, error, loading, refresh } = useResource<Asset>(`/api/v1/media/assets/${id}`)
  const [busy, setBusy] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const current = useRef<DownloadResource | null>(null)
  const submitting = useRef(false)
  useEffect(() => () => release(current.current), [])
  async function download() {
    if (!asset || submitting.current) return
    submitting.current = true
    release(current.current)
    const resource: DownloadResource = { controller: new AbortController(), url: '' }
    current.current = resource
    setBusy(true); setDownloadError('')
    try {
      // Reauthorize and read fresh, bounded, hash-checked bytes. Never reuse the preview.
      const blob = await imageBlob(asset, auth, resource.controller.signal)
      if (resource.controller.signal.aborted) return
      resource.url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = resource.url; link.download = `${asset.id}.png`
      document.body.append(link); link.click(); link.remove()
      resource.timer = setTimeout(() => release(resource), 60000)
    } catch (reason) {
      if (!resource.controller.signal.aborted) setDownloadError(problem(reason))
    } finally {
      submitting.current = false
      if (!resource.controller.signal.aborted) setBusy(false)
    }
  }
  return <><ResourceState loading={loading} error={error} retry={refresh} />{asset && <div className="asset-detail">
    <PrivateImage asset={asset} auth={auth} />
    <section className="asset-information"><h2>Изображение {asset.id.slice(0, 8)}</h2>
      <p>Файл получен из приватного серверного хранилища. Тестовый генератор создаёт PNG с отметкой TEST ONLY.</p>
      <dl className="summary-list"><div><dt>Размер</dt><dd>{asset.width} × {asset.height}</dd></div>
        <div><dt>Формат</dt><dd>PNG</dd></div><div><dt>Объём</dt><dd>{asset.byte_size.toLocaleString('ru-RU')} байт</dd></div>
        <div><dt>Создано</dt><dd>{new Date(asset.created_at * 1000).toLocaleString('ru-RU')}</dd></div></dl>
      <button className="primary full-width" disabled={busy} onClick={() => void download()}><Icon name="download" /> Скачать PNG</button>
      {downloadError && <p className="field-error" role="alert">{downloadError}</p>}
      <p>Удаление, публикация и использование файла как исходника пока не подключены. Архив доступен независимо от остатка баллов.</p>
      <Link href="/jobs">Открыть мои задания</Link>
    </section></div>}</>
}
export function AssetPage({ id }: { id: string }) {
  return <><Link className="back-link" href="/gallery"><Icon name="back" /> Мои работы</Link>
    <header className="page-heading"><p className="eyebrow">ПРИВАТНЫЙ ФАЙЛ</p><h1>Работа</h1></header>
    {!isId(id) ? <section className="gallery-empty"><h2>Работа не найдена</h2><Link href="/gallery">Вернуться в галерею</Link></section>
      : <WorkspaceGate>{auth => <Work id={id} auth={auth} />}</WorkspaceGate>}
  </>
}
