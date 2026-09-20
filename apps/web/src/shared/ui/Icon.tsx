import type { CSSProperties } from 'react'

const paths = {
  spark: 'm12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z',
  image: 'M4 4h16v16H4z M4 15l5-5 5 5 2-2 4 4 M16 8h.01',
  grid: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  feed: 'M4 5h16 M4 12h10 M4 19h16 M18 10l3 2-3 2',
  video: 'M3 6h12v12H3z M15 10l6-4v12l-6-4',
  audio: 'M4 10v4 M8 6v12 M12 3v18 M16 7v10 M20 10v4',
  cube: 'm12 3 9 5v9l-9 5-9-5V8z M3 8l9 5 9-5 M12 13v9',
  chat: 'M4 4h16v13H9l-5 4z M8 8h8 M8 12h5',
  arrow: 'M4 12h16 M14 6l6 6-6 6',
  back: 'M20 12H4 M10 6l-6 6 6 6',
  plus: 'M12 4v16 M4 12h16',
  close: 'm6 6 12 12 M18 6 6 18',
  panel: 'M6.2 4h11.6a2.7 2.7 0 0 1 2.7 2.7v10.6a2.7 2.7 0 0 1-2.7 2.7H6.2a2.7 2.7 0 0 1-2.7-2.7V6.7A2.7 2.7 0 0 1 6.2 4Z M9 4v16',
  edit: 'M13.5 5.5 18.5 10.5 M5 19l2.1-5.6L16.8 3.7a1.8 1.8 0 0 1 2.5 0l1 1a1.8 1.8 0 0 1 0 2.5l-9.7 9.7L5 19Z',
  more: 'M5 12h.01 M12 12h.01 M19 12h.01',
  chevron: 'm7.5 9.5 4.5 4.5 4.5-4.5',
  file: 'M7 3.8h7l4 4V20a1.8 1.8 0 0 1-1.8 1.8H7A1.8 1.8 0 0 1 5.2 20V5.6A1.8 1.8 0 0 1 7 3.8Z M14 3.8v4h4',
  globe: 'M20.5 12a8.5 8.5 0 1 1-17 0 8.5 8.5 0 1 1 17 0Z M3.8 12h16.4 M12 3.5c2.2 2.4 3.2 5.2 3.2 8.5s-1 6.1-3.2 8.5 M12 3.5C9.8 5.9 8.8 8.7 8.8 12s1 6.1 3.2 8.5',
  mic: 'M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z M6.5 11.5a5.5 5.5 0 0 0 11 0 M12 17v3',
  send: 'M12 19V5 M12 5l-5 5 M12 5l5 5',
  sun: 'M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2 M16 12a4 4 0 1 1-8 0 4 4 0 1 1 8 0',
  gem: 'm6.5 8.5 3-3h5l3 3-5.5 9-5.5-9Z M6.5 8.5h11 M9.5 5.5 12 8.5l2.5-3',
  download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
  search: 'M17 10a7 7 0 1 1-14 0 7 7 0 1 1 14 0 M15 15l6 6',
  lock: 'M6 10h12v11H6z M8 10V7a4 4 0 0 1 8 0v3',
  sliders: 'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
  clock: 'M21 12a9 9 0 1 1-18 0 9 9 0 1 1 18 0 M12 7v5l3 2',
  check: 'm4 12 5 5L20 6',
  user: 'M16 7a4 4 0 1 1-8 0 4 4 0 1 1 8 0 M4 21v-2a8 6 0 0 1 16 0v2',
  bin: 'M3 6h18 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 1 1 18 0 M12 11v6 M12 7h.01',
} as const
export type IconName = keyof typeof paths
export function Icon({ name, style }: { name: IconName; style?: CSSProperties }) {
  return <svg className="icon" data-icon={name} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>
}
