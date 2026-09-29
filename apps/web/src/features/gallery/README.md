# Web Gallery · локальная карта

Gallery — provider-neutral просмотр приватных Media assets. Browser никогда не должен обращаться к fal/provider URL напрямую.

| Видимый блок / задача | Основной файл | Ближайший test |
|---|---|---|
| Список работ / карточки | `Gallery.tsx` | `e2e/gallery.spec.ts` |
| Страница одной работы / действия | `AssetPage.tsx` | `e2e/gallery.spec.ts` |
| Session-bound preview/download bytes | `PrivateImage.tsx` | `e2e/gallery.spec.ts` |
| Grid/card/detail responsive CSS | `gallery.css` | gallery spec на affected viewport |
| Media API/ticket transport | `../../shared/workspace-api.ts` | gallery + backend media tests |

## Инварианты

- список metadata не означает право на bytes; private download остаётся session-bound;
- preview blob и download — не одно и то же доказательство целостности;
- Object URL освобождается при замене/unmount;
- чужой asset/некорректный ticket не получает fallback-копию;
- publish/delete/input-reference нельзя показывать работающими, пока backend contract отсутствует.

Для размера кнопки/карточки не читать Media backend. Если меняется ownership, ticket, MIME/hash или storage
semantics — перейти в `api.media` context route.
