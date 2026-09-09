import { navigation } from './navigation'

const details: Record<string, string> = {
  '/gallery': 'Здесь будут ваши изображения, видео, аудио и 3D-файлы. Личные материалы не станут публичными автоматически.',
  '/feed': 'Публикации появятся здесь только после явного решения автора. Лента и личная галерея — разные разделы.',
  '/account': 'Регистрация, вход и баланс появятся на следующем этапе. Сейчас форма входа намеренно не имитируется.',
  '/admin': 'Управление пользователями, моделями и заданиями будет защищено серверной проверкой прав. Сейчас административных данных и операций здесь нет.',
}

export function SectionPage({ path }: { path: string }) {
  const section = navigation.find(item => item.path === path)
  if (!section) return <section className="intro"><h1>Страница не найдена</h1><a href="/">Вернуться к обзору</a></section>
  return <section className="section-page">
    <p className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</p><h1>{section.title}</h1>
    <div className="empty-state"><span className="stage-label">В разработке</span>
      <h2>Раздел предусмотрен в новой платформе</h2>
      <p>{details[path] ?? 'Генерация пока не подключена. Следующий шаг — законченный сценарий с заданиями, учётом стоимости и сохранением результата.'}</p>
      <a className="text-link" href="/">Все направления <span aria-hidden="true">→</span></a>
    </div>
  </section>
}
