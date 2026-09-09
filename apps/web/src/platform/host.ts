export type HostKind = 'browser' | 'telegram' | 'max'

type HostWindow = Window & {
  Telegram?: { WebApp?: object }
  WebApp?: { initData?: string }
}

// Presentation hint only. NEVER use SDK presence or initDataUnsafe as identity.
// SDK initialization and server-side signed-init-data validation are separate work.
export function detectHost(target: Window): HostKind {
  const host = target as HostWindow
  if (host.Telegram?.WebApp) return 'telegram'
  if (host.WebApp) return 'max'
  return 'browser'
}
