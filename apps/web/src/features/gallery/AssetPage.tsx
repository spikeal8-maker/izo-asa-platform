import { useState } from 'react'
import { Link } from '../../shell/router'
import { Dialog } from '../../shared/ui/Dialog'
import { Icon } from '../../shared/ui/Icon'
import { useDemo } from '../prototype/DemoState'
import { artUrl } from '../prototype/art'
import './gallery.css'

export function AssetPage({ id }: { id: string }) {
  const { state, remove, updateDraft } = useDemo()
  const [deleting, setDeleting] = useState(false)
  const work = state.works.find(w => w.id === id)
  if (!work) return <section className="gallery-empty"><Icon name="image" /><h1>Работа не найдена</h1><p>Демо-пример удалён или отсутствует в этой вкладке.</p><Link className="primary" href="/gallery">Вернуться в галерею</Link></section>
  return <>
    <Link className="back-link" href="/gallery"><Icon name="back" /> Мои работы</Link>
    <div className="asset-detail"><div className="detail-image"><img src={artUrl(work.palette)} alt="Демонстрационный SVG, не AI-результат" style={{ aspectRatio: work.aspect.replace(':', '/') }} /><span>ПРЕДУСТАНОВЛЕННЫЙ ПРИМЕР</span></div>
      <section className="asset-information"><p className="eyebrow">РАБОТА / ДЕМО</p><h1>{work.title}</h1><p className="detail-disclaimer">Это векторный образец для проверки интерфейса. Настоящая генерация ещё не подключена.</p><dl className="summary-list"><div><dt>Модель интерфейса</dt><dd>{work.model === 'api-demo' ? 'Studio · API' : 'Studio · Local'}</dd></div><div><dt>Пропорции просмотра</dt><dd>{work.aspect}</dd></div><div><dt>Скачиваемый файл</dt><dd>SVG · исходный пример 1:1</dd></div><div><dt>Доступность</dt><dd>Демо этой вкладки</dd></div></dl>
        <label className="field-label" htmlFor="saved-prompt">Описание</label><textarea id="saved-prompt" readOnly value={work.prompt} rows={4} />
        <a className="primary full-width" href={artUrl(work.palette)} download="izo-demo-example.svg"><Icon name="download" /> Скачать SVG-пример</a>
        <Link className="secondary full-width" href="/image" onClick={() => updateDraft({ prompt: work.prompt, model: work.model, aspect: work.aspect, palette: work.palette })}><Icon name="spark" /> Использовать настройки</Link>
        <button className="text-danger" onClick={() => setDeleting(true)}><Icon name="bin" /> Удалить демо-работу</button>
      </section>
    </div>
    <Dialog open={deleting} title="Удалить этот демо-пример?" onClose={() => setDeleting(false)}><p>Пример исчезнет из этой вкладки. Настоящие файлы и сервер не затрагиваются.</p><button className="danger-button" onClick={() => { remove(id); setDeleting(false) }}>Удалить пример</button></Dialog>
  </>
}
