export const workspaces = [
  { id: 'chat', title: 'Чат', mark: 'Ч', description: 'Главная поверхность: разговор и запуск инструментов платформы.' },
  { id: 'image', title: 'Изображение', mark: 'И', description: 'От идеи и референсов — к готовому изображению.' },
  { id: 'video', title: 'Видео', mark: 'В', description: 'Анимация изображений и создание видеосцен.' },
  { id: 'audio', title: 'Звук', mark: 'А', description: 'Речь, музыка и работа с аудиоматериалами.' },
  { id: '3d', title: '3D', mark: '3D', description: 'Создание и просмотр трёхмерных объектов.' },
] as const

export const navigation = [
  { path: '/', title: 'Чат' },
  { path: '/studio/chat', title: 'Чат' },
  { path: '/feed', title: 'Лента' },
  ...workspaces.filter(w => w.id !== 'chat').map(w => ({ path: w.id === 'image' ? '/image' : `/studio/${w.id}`, title: w.title })),
  { path: '/gallery', title: 'Галерея' },
  { path: '/help', title: 'Помощь' },
  { path: '/account', title: 'Аккаунт' },
  { path: '/admin', title: 'Администрирование' },
]
