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
  sun: 'M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2 M16 12a4 4 0 1 1-8 0 4 4 0 1 1 8 0',
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
  return <svg className="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>
}
