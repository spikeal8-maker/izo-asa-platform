import { workspaces } from './navigation'

export function Overview() {
  return <>
    <section className="intro">
      <p className="eyebrow">ЕДИНОЕ ТВОРЧЕСКОЕ ПРОСТРАНСТВО</p>
      <h1>Ваша идея.<br />Все инструменты рядом.</h1>
      <p className="lead">Изображения, видео, звук, 3D и чат — в одной платформе.
        Сейчас мы проверяем её новое техническое основание.</p>
    </section>
    <section aria-labelledby="workspaces-title">
      <div className="section-heading"><h2 id="workspaces-title">Направления</h2><span>5 рабочих пространств</span></div>
      <div className="workspace-grid">
        {workspaces.map(w => <a className="workspace-card" href={`/studio/${w.id}`} key={w.id}>
          <span className="workspace-mark" aria-hidden="true">{w.mark}</span>
          <h3>{w.title}</h3><p>{w.description}</p><span className="card-caption">В разработке <span aria-hidden="true">↗</span></span>
        </a>)}
      </div>
    </section>
    <section className="foundation-panel" aria-labelledby="foundation-title">
      <div><p className="eyebrow">FOUNDATION 0</p><h2 id="foundation-title">Сначала надёжное основание</h2>
        <p>Общий интерфейс на всех экранах. Данные отдельно от приложения.
          Локальные модели и API — независимые исполнители.</p></div>
      <div className="foundation-tags"><span>Одна платформа</span><span>Приватные материалы</span><span>Проверяемые изменения</span></div>
    </section>
  </>
}
