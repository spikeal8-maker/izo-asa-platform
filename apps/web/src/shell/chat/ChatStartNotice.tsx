import type { AuthView, CredentialView } from '../../shared/api'
import type { ChatDisplayPolicy } from './modelCatalog'
import { Link } from '../router'

export function ChatStartNotice({ auth, credentials, policy }: {
  auth: AuthView | null | undefined
  credentials: CredentialView[]
  policy: ChatDisplayPolicy | null
}) {
  if (auth === undefined) {
    return <p className="chat-start-note" role="status">Проверяем вход…</p>
  }
  if (!auth) {
    return <p className="chat-start-note">
      Для сохранённого разговора нужен аккаунт. <Link href="/login">Войти</Link>
    </p>
  }
  const personal = credentials.some(item => item.verified)
  const platform = policy?.models.some(item => item.provider === 'platform') ?? false
  if (platform) {
    return <p className="chat-start-note">
      Доступна тестовая платформенная модель. Свой API-ключ необязателен.
    </p>
  }
  if (!personal) {
    return <p className="chat-start-note">
      Подключите и проверьте API key провайдера.
    </p>
  }
  return null
}
