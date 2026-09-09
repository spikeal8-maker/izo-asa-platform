import { useState } from 'react'
import { Link } from '../../shell/router'
import { Icon } from '../../shared/ui/Icon'
import { WorkspaceGate, ResourceState, useResource } from '../../shared/workspace'
import { type Assets } from '../../shared/workspace-api'
import './gallery.css'

function Works() {
  const [offset, setOffset] = useState(0)
  const [query, setQuery] = useState('')
  const { data, error, loading, refresh } = useResource<Assets>(`/api/v1/media/assets?limit=20&offset=${offset}`)
  const works = data?.assets.filter(asset => `${asset.id} ${asset.width}x${asset.height}`.includes(query.trim().toLowerCase())) ?? []
  return <><ResourceState error={error} loading={loading} retry={refresh} />
    {data && <><div className="gallery-toolbar"><p>PNG · приватные файлы</p>
      <label className="search-box"><Icon name="search" /><input aria-label="Поиск на этой странице" placeholder="Код или размер"
        value={query} maxLength={100} onChange={event => setQuery(event.target.value)} /></label></div>
      <p className="gallery-meta"><Icon name="lock" /> Только ваш серверный аккаунт
        <span>Занято: {data.used_bytes.toLocaleString('ru-RU')} байт · резерв: {data.reserved_bytes.toLocaleString('ru-RU')}</span></p>
      {works.length ? <div className="gallery-grid">{works.map(asset => <Link className="asset-card" href={`/gallery/${asset.id}`} key={asset.id}>
        <div className="asset-thumbnail server-thumbnail"><Icon name="image" /><span>PNG · {asset.width} × {asset.height}</span></div>
        <div className="asset-card-copy"><strong>Изображение {asset.id.slice(0, 8)}</strong>
          <small>{new Date(asset.created_at * 1000).toLocaleString('ru-RU')}<span>{Math.ceil(asset.byte_size / 1024)} КБ</span></small></div>
      </Link>)}</div> : <section className="gallery-empty"><div className="empty-icon"><Icon name="grid" /></div>
        <h2>{data.assets.length ? 'Ничего не найдено на этой странице' : 'Здесь начнётся ваша коллекция'}</h2>
        <p>{data.assets.length ? 'Измените поиск. Сохранённые файлы не удалены.' : 'В галерее пока нет сохранённых файлов. Создайте задание в студии.'}</p>
        {data.assets.length ? <button onClick={() => setQuery('')}>Сбросить поиск</button> : <Link className="primary" href="/image">Открыть студию</Link>}</section>}
      <div className="workspace-actions">{offset > 0 && <button onClick={() => { setOffset(Math.max(0, offset - 20)); setQuery('') }}>Предыдущая страница</button>}
        {data.next_offset !== null && <button onClick={() => { setOffset(data.next_offset!); setQuery('') }}>Следующая страница</button>}
        <button onClick={refresh}>Обновить галерею</button></div>
      <p className="prototype-note">Полное изображение загружается только при открытии работы. Уменьшенные превью, удаление и публикация ещё не подключены.</p></>}
  </>
}
export function Gallery() {
  return <><header className="page-heading gallery-heading"><div><p className="eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</p>
    <h1>Галерея</h1><p>Приватные файлы сохраняются на сервере и доступны после повторного входа.</p></div>
    <Link className="primary" href="/image"><Icon name="plus" /> Создать изображение</Link></header>
    <WorkspaceGate>{() => <Works />}</WorkspaceGate></>
}
