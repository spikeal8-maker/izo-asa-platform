# Web Studio / Result · локальная карта

Studio и ResultPanel используют общий server Account/Credits/Entitlements/Jobs/Media contract. UI не знает provider
secret/URL и не имеет собственного ledger. Provider-specific lifecycle документируется в backend providers/jobs.

| Видимый блок / задача | Основной owner | Ближайший test |
|---|---|---|
| Page heading и guest/auth композиция | `Studio.tsx` | `e2e/studio.spec.ts`, `guest.spec.ts` |
| Capability/model selector, prompt, size | `Composer.tsx` | `e2e/studio.spec.ts`, `provider.spec.ts` |
| Quote/подтверждение/кнопка запуска | `Composer.tsx` + `studio.css` | `studio.spec.ts` |
| Pending operation ID / lost response | `../../shared/submission.ts` + `Composer.tsx` | lost-response cases in `studio.spec.ts` |
| Guest trial | `GuestTrial.tsx` | `guest.spec.ts` |
| Jobs list/detail/status/cancel | `ResultPanel.tsx` | `studio.spec.ts` |
| Общий jobs/credits transport | `../../shared/workspace-api.ts` | affected studio/provider specs |
| Responsive Studio/Result CSS | `studio.css` | affected viewport in studio spec |

## Инварианты

- server plan определяет доступные capability/executor/limits;
- quote определяет authoritative product Credits reserve; browser не считает цену сам;
- submit отправляет server quote + stable operation ID, а не owner/provider/connection/price;
- network/unknown response не создаёт новый operation ID автоматически;
- provider uncertainty/reconciliation — server state; UI не обещает локальный refund;
- result становится обычным private Media asset; browser не скачивает provider URL напрямую;
- unsupported image modes/references/delete/publish не изображаются работающими.

## Когда расширять контекст

Текст/CSS/расположение формы или кнопки: начинай с `Composer.tsx` и оставайся в web Studio route. Page shell/guest gate:
`Studio.tsx` + `GuestTrial.tsx`. Изменение entitlement/price → `api.entitlements` / `api.credits`. Изменение Job
cancel/retry/reconcile → `api.jobs`. Provider HTTP/request ID/paid retry → `api.provider_execution`. Ownership/download →
`api.media`.

Локальная проверка: `npm run build` и `npx playwright test e2e/studio.spec.ts e2e/provider.spec.ts e2e/guest.spec.ts`
с нужными projects. Backend semantics не считаются проверенными mocked browser fixture; для них запускается профильный Python test.
