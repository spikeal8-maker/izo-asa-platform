import { Dialog } from '../../shared/ui/Dialog'
import type { Quote } from '../../shared/workspace-api'

export function QuoteDialog({ quote, busy, expired, onClose, onSubmit }: {
  quote: Quote | null
  busy: boolean
  expired: boolean
  onClose: () => void
  onSubmit: () => void
}) {
  return <Dialog open={!!quote} title="Создать изображение?" onClose={() => { if (!busy) onClose() }}>
    {quote && <><p>{quote.test_only ? 'Пробный режим: результат создаётся без внешней AI-модели.' : quote.notice}</p>
      <dl className="summary-list">
        <div><dt>Размер</dt><dd>{quote.width} × {quote.height}</dd></div>
        <div><dt>Баллы для запуска</dt><dd id="quote-reserve">{quote.credits} балл.</dd></div>
        <div><dt>Режим</dt><dd>{quote.test_only ? 'Пробный' : 'AI'}</dd></div>
      </dl>
      <p className="quote-prompt">{quote.prompt}</p>
      {expired && <p role="alert">Расчёт устарел. Закройте окно и повторите.</p>}
      <button className="primary full-width quote-submit" aria-label="Подтвердить создание"
        aria-describedby="quote-reserve" disabled={busy || expired} onClick={onSubmit}>
        <span>Подтвердить создание</span>
        <small data-testid="quote-submit-price" aria-hidden="true">Резерв: {quote.credits} балл.</small>
      </button></>}
  </Dialog>
}
