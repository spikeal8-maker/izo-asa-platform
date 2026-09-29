export const workspaces = [
  { id: 'chat', path: '/', title: 'Чат', mobileTitle: 'Чат', mark: 'Ч', description: 'Главная поверхность: разговор и запуск инструментов платформы.' },
  { id: 'image', path: '/image', title: 'Изображение', mobileTitle: 'Изо', mark: 'И', description: 'От идеи и референсов — к готовому изображению.' },
  { id: 'video', path: '/video', title: 'Видео', mobileTitle: 'Видео', mark: 'В', description: 'Анимация изображений и создание видеосцен.' },
  { id: 'audio', path: '/audio', title: 'Звук', mobileTitle: 'Звук', mark: 'А', description: 'Речь, музыка и работа с аудиоматериалами.' },
  { id: '3d', path: '/3d', title: '3D', mobileTitle: '3D', mark: '3D', description: 'Создание и просмотр трёхмерных объектов.' },
] as const

export const routeAliases: Record<string, string> = {
  '/studio/chat': '/',
  '/studio/image': '/image',
  '/studio/video': '/video',
  '/studio/audio': '/audio',
  '/studio/3d': '/3d',
}

export function canonicalRoute(path: string) {
  return routeAliases[path] ?? path
}

export const navigation = [
  ...workspaces.map(({ path, title }) => ({ path, title })),
  { path: '/feed', title: 'Лента' },
  { path: '/gallery', title: 'Галерея' },
  { path: '/help', title: 'Помощь' },
  { path: '/account', title: 'Аккаунт' },
  { path: '/admin', title: 'Администрирование' },
]
