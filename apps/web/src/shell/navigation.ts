export const workspaces = [
  { id: 'image', title: 'Изображения', mark: 'И', description: 'От идеи и референсов — к готовому изображению.' },
  { id: 'video', title: 'Видео', mark: 'В', description: 'Анимация изображений и создание видеосцен.' },
  { id: 'audio', title: 'Звук', mark: 'А', description: 'Речь, музыка и работа с аудиоматериалами.' },
  { id: '3d', title: '3D', mark: '3D', description: 'Создание и просмотр трёхмерных объектов.' },
  { id: 'chat', title: 'Чат', mark: 'Ч', description: 'Помощник, объединяющий инструменты платформы.' },
] as const
export const navigation = [
  { path: '/', title: 'Обзор' },
  ...workspaces.map(w => ({ path: `/studio/${w.id}`, title: w.title })),
  { path: '/gallery', title: 'Галерея' },
  { path: '/feed', title: 'Лента' },
  { path: '/account', title: 'Аккаунт' },
  { path: '/admin', title: 'Администрирование' },
]
