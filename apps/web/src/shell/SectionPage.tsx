import { navigation } from './navigation'
import { Link } from './router'

const details: Record<string, { lead: string; cards: [string, string][] }> = {
  '/studio/video': { lead: 'Собирайте короткие сцены из текста и изображений.', cards: [['Изображение → видео', 'Оживление готового кадра и управление движением.'], ['Текст → сцена', 'Описание идеи, длительности и композиции.'], ['Проекты', 'Будущие видео будут сохраняться рядом с другими работами.']] },
  '/studio/audio': { lead: 'Работайте с голосом, музыкой и аудиоматериалами в одном пространстве.', cards: [['Озвучка', 'Текст, голос и готовый аудиофайл.'], ['Музыка', 'Идея, настроение и длительность.'], ['Распознавание', 'Загрузка записи и работа с полученным текстом.']] },
  '/studio/3d': { lead: 'Создавайте и просматривайте трёхмерные идеи без отдельной навигации.', cards: [['Изображение → 3D', 'Исходный кадр как отправная точка модели.'], ['Текст → объект', 'Описание формы, материалов и назначения.'], ['Просмотр', 'Интерактивный viewer и скачивание поддерживаемых форматов.']] },
  '/studio/chat': { lead: 'Чат связывает идеи и инструменты: обсудите задачу, уточните промпт и перейдите к созданию.', cards: [['Идея', 'Сформулируйте задачу обычным языком.'], ['Подготовка', 'Получите структуру, варианты и точный промпт.'], ['Инструменты', 'Из чата можно будет запускать изображение, видео, аудио и 3D.']] },
}

export function SectionPage({ path }: { path: string }) {
  const section = navigation.find(item => item.path === path)
  const content = details[path]
  if (!section || !content) return <section className="intro"><h1>Страница не найдена</h1><Link className="text-link" href="/">Вернуться в ленту</Link></section>
  return <section className="section-page">
    <p className="eyebrow">СТУДИЯ</p><h1>{section.title}</h1><p>{content.lead}</p>
    <div className="workspace-preview">{content.cards.map(([title, text]) => <div key={title}><h2>{title}</h2><p>{text}</p></div>)}</div>
    <p style={{ marginTop: 26 }}><Link className="text-link" href="/image">Перейти к доступному режиму изображений <span aria-hidden="true">→</span></Link></p>
  </section>
}
