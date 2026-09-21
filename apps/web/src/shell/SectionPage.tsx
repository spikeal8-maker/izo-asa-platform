import { navigation } from './navigation'
import { Link } from './router'

const details: Record<string, { lead: string; cards: [string, string][] }> = {
  '/video': { lead: 'Собирайте короткие сцены из текста и изображений.', cards: [['Изображение → видео', 'Оживление готового кадра и управление движением.'], ['Текст → сцена', 'Описание идеи, длительности и композиции.'], ['Проекты', 'Будущие видео будут сохраняться рядом с другими работами.']] },
  '/audio': { lead: 'Работайте с голосом, музыкой и аудиоматериалами в одном пространстве.', cards: [['Озвучка', 'Текст, голос и готовый аудиофайл.'], ['Музыка', 'Идея, настроение и длительность.'], ['Распознавание', 'Загрузка записи и работа с полученным текстом.']] },
  '/3d': { lead: 'Создавайте и просматривайте трёхмерные идеи без отдельной навигации.', cards: [['Изображение → 3D', 'Исходный кадр как отправная точка модели.'], ['Текст → объект', 'Описание формы, материалов и назначения.'], ['Просмотр', 'Интерактивный viewer и скачивание поддерживаемых форматов.']] },
  '/help': { lead: 'Короткие подсказки по основным разделам ИЗО АСА.', cards: [['Чат', 'Опишите задачу обычным языком. Прямые инструменты для изображений, видео, звука и 3D доступны отдельными разделами.'], ['Изображение', 'Используйте отдельную студию для уже работающей серверной генерации изображений.'], ['Галерея', 'Ваши сохранённые результаты находятся в личной галерее.']] },
}

export function SectionPage({ path }: { path: string }) {
  const section = navigation.find(item => item.path === path)
  const content = details[path]
  if (!section || !content) return <section className="intro"><h1>Страница не найдена</h1><Link className="text-link" href="/">Вернуться в чат</Link></section>
  return <section className="section-page">
    <p className="eyebrow">ИЗО АСА</p><h1>{section.title}</h1><p>{content.lead}</p>
    <div className="workspace-preview">{content.cards.map(([title, text]) => <div key={title}><h2>{title}</h2><p>{text}</p></div>)}</div>
    {path !== '/help' && <p style={{ marginTop: 26 }}><Link className="text-link" href="/">Вернуться в чат <span aria-hidden="true">→</span></Link></p>}
  </section>
}
