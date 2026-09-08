import { useState } from 'react'
import { Link } from '../../shell/router'
import { Icon } from '../../shared/ui/Icon'
import { useDemo } from '../prototype/DemoState'
import { artUrl } from '../prototype/art'
import './gallery.css'

const filters = [['all', 'Все работы'], ['api-demo', 'API · демо'], ['local-demo', 'Local · демо']] as const

export function Gallery() {
  const { state } = useDemo()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<string>('all')
  const works = state.works.filter(work =>
    (filter === 'all' || filter === work.model) && work.title.toLowerCase().includes(query.toLowerCase()))

  return <>
    <header className="page-heading gallery-heading">
      <div>
        <p className="eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</p>
        <h1>Галерея</h1>
        <p>Ваши идеи, к которым хочется вернуться.</p>
      </div>
      <Link className="primary" href="/image"><Icon name="plus" /> Создать демо</Link>
    </header>
    <div className="gallery-toolbar">
      <div className="filter-tabs" aria-label="Фильтр работ">
        {filters.map(([id, title]) => <button
          key={id} aria-pressed={filter === id}
          className={filter === id ? 'selected' : ''} onClick={() => setFilter(id)}
        >{title}</button>)}
      </div>
      <label className="search-box">
        <Icon name="search" />
        <input aria-label="Поиск работ" placeholder="Найти работу" value={query}
          onChange={event => setQuery(event.target.value)} maxLength={100} />
      </label>
    </div>
    <p className="gallery-meta">
      <Icon name="lock" /> Только демо этой вкладки
      <span>{works.length} из {state.works.length} работ</span>
    </p>
    {works.length ? <div className="gallery-grid">
      {works.map(work => <Link className="asset-card" href={`/gallery/${work.id}`} key={work.id}>
        <div className="asset-thumbnail">
          <img src={artUrl(work.palette)} alt={work.title} loading="lazy" />
          <span>SVG · ДЕМО</span>
        </div>
        <div className="asset-card-copy">
          <strong>{work.title}</strong>
          <small>{work.model === 'api-demo' ? 'Studio · API' : 'Studio · Local'}<span>{work.aspect}</span></small>
        </div>
      </Link>)}
    </div> : <section className="gallery-empty">
      <div className="empty-icon"><Icon name="grid" /></div>
      <h2>{state.works.length ? 'Ничего не найдено' : 'Здесь начнётся ваша коллекция'}</h2>
      <p>{state.works.length
        ? 'Измените запрос или фильтр. Работы не удалены.'
        : 'Создайте первый демонстрационный результат в студии. В настоящем сервисе здесь будут ваши приватные работы.'}</p>
      {state.works.length
        ? <button className="secondary" onClick={() => { setQuery(''); setFilter('all') }}>Сбросить фильтры</button>
        : <Link className="primary" href="/image">Открыть студию <Icon name="arrow" /></Link>}
    </section>}
    <p className="prototype-note">
      Прототип · не облачная галерея. Закрытие вкладки или сброс демо может удалить эти примеры.
    </p>
  </>
}
