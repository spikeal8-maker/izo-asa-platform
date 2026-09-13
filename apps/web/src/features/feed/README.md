# Feed · локальная карта feature

Feed — публичная стартовая поверхность и визуальный Explore. UX-002 делает `/` и `/feed` первым экраном продукта.
До FEED-001 здесь разрешены только явно presentation-примеры: они не считаются публикациями пользователей и не используют private Media.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| Hero / quick start / продуктовый первый экран | `FeedPage.tsx` | `apps/web/e2e/shell.spec.ts` |
| Feed presentation grid и responsive 2K/4K/8K | `feed.css` | `apps/web/e2e/shell.spec.ts` |
| Primary Feed route / sidebar selection | `../../shell/App.tsx` | `apps/web/e2e/shell.spec.ts` |

## Инварианты

- Feed доступен без login и не раскрывает private account/media данные.
- До FEED-001 примеры явно являются presentation-контентом и не имитируют реальных авторов, likes или публикации.
- Registration/auth не принадлежит Feed: это `web.accounts` / `api.accounts`.
- Реальные публикации, author metadata, reactions/remix и moderation появятся только вместе с FEED-001 contract.
- На телефоне visual grid остаётся читаемым без horizontal overflow; на широком desktop grid использует пространство, а reading text остаётся ограниченным.

## Когда расширять контекст

Shell/navigation/theme → `web.shell`; реальные media/publication semantics → будущий FEED-001 + `api.media`; account/signup → `web.accounts` / `api.accounts`.
