import { useState } from 'react'
import { Link } from '../../shell/router'
import { Icon } from '../../shared/ui/Icon'
import type { AuthView } from '../../shared/api'
import { WorkspaceGate, ResourceState, useResource } from '../../shared/workspace'
import { type Asset, isId, downloadTicket, problem } from '../../shared/workspace-api'
import { PrivateImage } from './PrivateImage'
import './gallery.css'

function Work({ id, auth }: { id: string; auth: AuthView }) {
  const { data: asset, error, loading, refresh } = useResource<Asset>(`/api/v1/media/assets/${id}`)
  const [busy, setBusy] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  async function download() {
    if (!asset || busy) return
    setBusy(true); setDownloadError('')
    try {
      // Always obtain a new session-bound ticket. Do not download the old preview blob.
      const url = await downloadTicket(asset, auth)
      const link = document.createElement('a')
      link.href = url; link.download = `${asset.id}.png`; link.referrerPolicy = 'no-referrer'
      document.body.append(link); link.click(); link.remove()
    } catch (reason) { setDownloadError(problem(reason)) }
    finally { setBusy(false) }
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
