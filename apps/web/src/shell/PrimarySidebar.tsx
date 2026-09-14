import { Icon, type IconName } from '../shared/ui/Icon'
import { AdminLink } from '../features/admin/AdminPage'
import type { AuthView } from '../shared/api'
import { Link } from './router'

const items: { href: string; title: string; icon: IconName }[] = [
  { href: '/', title: 'Лента', icon: 'feed' },
  { href: '/image', title: 'Студия', icon: 'spark' },
  { href: '/gallery', title: 'Галерея', icon: 'grid' },
]

export function PrimarySidebar({ path, auth }: { path: string; auth: AuthView | null | undefined }) {
  const feed = path === '/' || path === '/feed'
  const studio = ['/image', '/studio/image'].includes(path)
  const gallery = path === '/gallery' || path.startsWith('/gallery/')
  const active = (href: string) => href === '/' ? feed : href === '/image' ? studio : gallery

  return <aside className="sidebar">
    <Link href="/" className="brand" aria-label="ИЗО АСА — лента">
      <span className="brand-mark"><Icon name="spark" /></span><span>ИЗО АСА</span>
    </Link>
    <nav aria-label="Основные разделы">{items.map(item => <Link href={item.href} key={item.href}
      aria-label={item.title} className={active(item.href) ? 'active' : ''}
      aria-current={active(item.href) ? 'page' : undefined}><Icon name={item.icon} /><span>{item.title}</span></Link>)}</nav>
    <div className="sidebar-bottom">
      <Link href="/account/credits" className="side-link">Баланс</Link>
      <Link href="/account" className="side-link">Аккаунт</Link>
      {auth && <AdminLink path={path} />}
    </div>
  </aside>
}
