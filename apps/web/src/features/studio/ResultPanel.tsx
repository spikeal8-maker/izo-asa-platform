import { useState } from 'react'
import { Icon } from '../../shared/ui/Icon'
import { Dialog } from '../../shared/ui/Dialog'
import { Link } from '../../shell/router'
import { artUrl } from '../prototype/art'
import { useDemo } from '../prototype/DemoState'

export function ResultPanel() {
  const { state, cancel } = useDemo()
  const [confirmCancel, setConfirmCancel] = useState(false)
  const job = state.job
  const complete = job?.state === 'succeeded'
  const active = job?.state === 'running'
  const ratio = job?.aspect ?? state.draft.aspect
  return <section className="result-panel" aria-labelledby="preview-title">
    <div className="panel-heading"><h2 id="preview-title">{complete ? 'Результат демо' : active ? 'Подготовка примера' : 'Пространство для результата'}</h2><span className="quiet-pill">{ratio}</span></div>
    <div className="art-stage">
      <img src={artUrl(job?.palette ?? state.draft.palette)} alt="Демонстрационная векторная композиция: арка у воды" className={active ? 'art-image processing' : 'art-image'} style={{ aspectRatio: ratio.replace(':', '/') }} />
      <span className="art-label">ПРИМЕР · НЕ AI-ГЕНЕРАЦИЯ</span>
      {active && <div className="result-overlay"><span className="spinner" /><strong>Проверяем сценарий ожидания</strong><span>Сейчас показывается тестовая последовательность</span><button className="secondary" onClick={() => setConfirmCancel(true)}>Отменить демо</button></div>}
      {(job?.state === 'failed' || job?.state === 'cancelled') && <div className="result-overlay"><Icon name="info" /><strong>{job.state === 'failed' ? 'Тестовая ошибка провайдера' : 'Демо отменено'}</strong><span>Демо-баллы не списаны. Можно повторить запуск.</span></div>}
    </div>
    <div className="result-caption" aria-live="polite">
      <div><strong>{complete ? 'Пример сохранён в этой вкладке' : 'Геометрия тишины'}</strong><p>{complete ? 'Предустановленный SVG, не результат модели. Откройте его в галерее.' : 'Оригинальный векторный пример для оценки интерфейса. Настоящий AI появится на следующем этапе.'}</p></div>
      {complete && <Link className="primary" href={`/gallery/${job.id}`}>Открыть работу <Icon name="arrow" /></Link>}
    </div>
    <Dialog open={confirmCancel} title="Отменить тестовую задачу?" onClose={() => setConfirmCancel(false)}><p>В этом макете внешнего запроса нет. Демо-резерв будет освобождён.</p><button className="primary" onClick={() => { cancel(); setConfirmCancel(false) }}>Да, отменить демо</button></Dialog>
  </section>
}
