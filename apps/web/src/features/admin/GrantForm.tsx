import { useRef, useState, type FormEvent } from 'react'
import type { components } from '../../shared/api.generated'
import { apiRequest, ApiError } from '../../shared/api'
import { Dialog } from '../../shared/ui/Dialog'

type User = components['schemas']['AdminUser']
type Receipt = components['schemas']['CompensationReceipt']
const errors: Record<string, string> = {
  source_already_used: 'Эта заявка уже оплачена. Проверьте журнал; не создавайте новую заявку для повторного начисления.',
  idempotency_conflict: 'Повтор отличается от принятой операции. Проверьте журнал.',
  grant_forbidden: 'Сумма превышает текущий лимит или право начисления отозвано.',
  forbidden: 'Полномочия изменились. Обновите страницу.',
  auth_required: 'Сессия завершена. Войдите заново.',
  reauth_required: 'Не удалось подтвердить текущий пароль. Повторите вход или проверку.',
  verification_required: 'Сначала подтвердите почту административного аккаунта.',
  csrf_rejected: 'Проверка сессии не пройдена. Обновите страницу.',
  rate_limited: 'Достигнут лимит попыток подтверждения. Сделайте паузу.',
  account_restricted: 'Получатель сейчас не может получить начисление.',
}

export function GrantForm({ user, maximum, csrf, onGranted }: {
  user: User; maximum: number; csrf: string; onGranted: () => void
}) {
  const [pending, setPending] = useState<{ amount: number; case_reference: string; operation_id: string } | null>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const previous = useRef<{ fingerprint: string; id: string } | null>(null)

  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inFlight.current) return
    const data = new FormData(event.currentTarget)
    const reference = String(data.get('case_reference') ?? '').trim().toUpperCase()
    const amount = Number(data.get('amount'))
    if (!Number.isSafeInteger(amount) || amount < 1 || amount > maximum
        || !/^[A-Z0-9][A-Z0-9._-]{2,63}$/.test(reference)) {
      setError('Проверьте номер заявки и целое число баллов в пределах лимита.'); return
    }
    const fingerprint = JSON.stringify([user.id, reference, amount])
    if (previous.current?.fingerprint !== fingerprint) previous.current = { fingerprint, id: crypto.randomUUID() }
    setPending({ amount, case_reference: reference, operation_id: previous.current.id })
    setError(''); setReceipt(null)
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!pending || inFlight.current) return
    const form = event.currentTarget
    const input = form.elements.namedItem('current_password') as HTMLInputElement
    const body = { ...pending, current_password: input.value }
    input.value = ''
    inFlight.current = true; setBusy(true); setError('')
    try {
      const result = await apiRequest<Receipt>(`/api/v1/admin/users/${user.id}/compensations`,
        { method: 'POST', data: body, csrf })
      setReceipt(result); setPending(null); onGranted()
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status < 500
        ? errors[reason.code] ?? 'Операция отклонена сервером. Проверьте данные и журнал.'
        : 'Ответ не получен. Результат неизвестен: проверьте журнал или повторите ту же операцию. Не меняйте номер заявки.')
    } finally {
      body.current_password = ''; inFlight.current = false; setBusy(false)
    }
  }

  return <section className="admin-grant" aria-label="Компенсация">
    <h2>Начислить компенсацию</h2>
    <p>Только по реальной заявке. Лимит одного начисления: {maximum.toLocaleString('ru-RU')} баллов.</p>
    <form onSubmit={prepare} className="admin-form">
      <label>Номер заявки<input name="case_reference" required minLength={3} maxLength={64}
        pattern="[A-Za-z0-9][A-Za-z0-9._\-]{2,63}" autoComplete="off" />
        <small>Стабильный номер обращения, например MIG-123. Без адреса почты и персональных данных.</small></label>
      <label>Количество баллов<input name="amount" type="number" required min={1} max={maximum} step={1} /></label>
      <button className="primary" disabled={busy || maximum < 1}>Проверить начисление</button>
    </form>
    {error && !pending && <p className="field-error" role="alert">{error}</p>}
    {receipt && <div className="admin-receipt" role="status">
      <strong>Начислено {receipt.entry.balance_delta} баллов</strong>
      <p>Заявка {receipt.case_reference}. Операция {receipt.entry.operation_id}.</p>
      <p>Это серверная запись. Повтор того же запроса не начисляет ещё раз.</p>
    </div>}
    <Dialog open={pending !== null} title="Подтверждение компенсации" onClose={() => { if (!inFlight.current) setPending(null) }}>
      {pending && <form onSubmit={confirm} className="admin-form">
        <p>Получатель: <strong>{user.display_name}</strong>, код <strong>{user.public_code}</strong>.</p>
        <p>Заявка {pending.case_reference}: <strong>{pending.amount} баллов</strong>.</p>
        <label>Текущий пароль администратора<input name="current_password" type="password"
          required autoComplete="current-password" maxLength={128} disabled={busy} /></label>
        {error && <p className="field-error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={busy}>{busy ? 'Проверяем сервер…' : 'Подтвердить начисление'}</button>
      </form>}
    </Dialog>
  </section>
}
