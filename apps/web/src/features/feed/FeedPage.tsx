import { Link } from '../../shell/router'
import './feed.css'

const examples = [
  { title: 'Редакционная съёмка', type: 'Изображение', className: 'sample-a', prompt: 'Минималистичная предметная сцена, мягкий свет' },
  { title: 'Город после дождя', type: 'Изображение', className: 'sample-b', prompt: 'Ночной город, мокрый асфальт, отражения' },
  { title: 'Обложка проекта', type: 'Дизайн', className: 'sample-c', prompt: 'Графичная обложка, крупная форма, чистый фон' },
  { title: 'Архитектурная идея', type: '3D / концепт', className: 'sample-d', prompt: 'Современный павильон в спокойной среде' },
  { title: 'Короткая сцена', type: 'Видео / концепт', className: 'sample-e', prompt: 'Плавное движение камеры и мягкий свет' },
  { title: 'Работа с идеей', type: 'Чат', className: 'sample-f', prompt: 'Разобрать идею и подготовить точный промпт' },
]

export function FeedPage() {
  return <section className="feed-page">
    <header className="feed-hero">
      <div className="feed-hero-copy">
        <p className="eyebrow">ИЗО АСА</p>
        <h1>Создавайте, смотрите и развивайте идеи.</h1>
        <p>Одно пространство для изображений, видео, звука, 3D и чата. Лента открыта для просмотра, а рабочие инструменты всегда рядом.</p>
        <div className="feed-actions">
          <Link className="primary" href="/image">Создать изображение</Link>
          <Link className="secondary" href="/studio/chat">Открыть чат</Link>
        </div>
      </div>
      <div className="quick-start" aria-label="Быстрый старт">
        <span>Что хотите сделать?</span>
        <p>Опишите идею — начните с изображения или откройте чат.</p>
        <div><Link href="/image">Изображение <b aria-hidden="true">→</b></Link><Link href="/studio/chat">Чат <b aria-hidden="true">→</b></Link></div>
      </div>
    </header>

    <div className="feed-heading">
      <div><p className="eyebrow">ЛЕНТА</p><h2>Подборка идей</h2></div>
      <p>Здесь будут публичные работы пользователей. Пока показываем направление визуальной сетки без выдачи примеров за реальные публикации.</p>
    </div>
    <div className="feed-grid">{examples.map((item, index) => <article className="feed-card" key={item.title}>
      <div className={`sample-art ${item.className}`} role="img" aria-label={`Визуальный пример: ${item.title}`}><span>{String(index + 1).padStart(2, '0')}</span></div>
      <div className="feed-card-body"><small>{item.type}</small><h3>{item.title}</h3><p>{item.prompt}</p></div>
    </article>)}</div>

    <section className="about-product">
      <div><p className="eyebrow">ПЛАТФОРМА</p><h2>От идеи до результата — без лишних переходов.</h2></div>
      <p>Создавайте в студии, храните результаты в галерее и публикуйте выбранные работы в ленту. Аккаунт нужен для сохранения истории и продолжения работы между устройствами.</p>
    </section>
  </section>
}
