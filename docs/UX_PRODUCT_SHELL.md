# IZO ASA · Product Shell + Semantic Color System v1.1

Статус: обязательное продуктовое ТЗ текущего frontend. Решение владельца заменяет прежний feed-first shell UX-002 там,
где они расходятся. Главная поверхность продукта — Chat; Feed остаётся отдельным публичным разделом.

## 1. Главная поверхность

- `/` — **Чат**. `/studio/chat` сохраняется как совместимый alias.
- Чат является основной точкой входа в ИЗО АСА: обычный диалог + запуск Image/Video/Audio/3D из одного composer.
- `/feed` — отдельная Лента/Explore; `/gallery` — личная Галерея.
- Верхняя продуктовая полоса на всех основных пользовательских поверхностях: **Чат → Изображение → Видео → Звук → 3D**.
- Лента, Галерея, Помощь, токены/баланс и Account являются utility navigation, а не отдельными creative modes.
- Недоступный runtime нельзя изображать успешным. Пока server text-chat отсутствует, frontend может показать composer/navigation,
  но не генерирует fake assistant answer. Рабочая image generation остаётся на существующем Jobs/Media path.

## 2. Chat geometry

Desktop reference:
- sidebar: около `260px`;
- top header: `56px`;
- reading/chat measure: `768px`;
- composer measure: `768px`;
- assistant text без тяжёлой карточки; user message — спокойный neutral bubble;
- composer закреплён внизу chat surface и не перекрывает сообщения;
- sidebar и product header используют тот же shell на остальных страницах.

Mobile reference:
- верхняя область — две строки: context/account + горизонтальная полоса creative modes;
- короткая нижняя navigation: Chat / Feed / Gallery;
- composer учитывает `safe-area-inset-bottom` и экранную клавиатуру;
- hover-preview не является единственным способом доступа к функции.

## 3. Semantic Color System v1.1

`apps/web/src/shell/theme.css` — runtime source of truth. Все страницы используют только semantic tokens ниже.
При смене утверждённого цвета меняется токен, а не отдельные компоненты.

### Light

```css
--color-bg: #F6F6F8;
--color-surface: #FFFFFF;
--color-border: #D7DAE0;
--color-text: #181A1F;
--color-text-secondary: #4F5660;
--color-brand: #6E45C1;
--color-brand-soft: #F0ECF7;
--color-on-brand: #FFFFFF;
--color-success: #176B4A;
--color-warning: #8A5A00;
--color-error: #B73748;
```

### Dark

```css
--color-bg: #111318;
--color-surface: #191C22;
--color-border: #343A45;
--color-text: #F3F4F6;
--color-text-secondary: #B0B6C0;
--color-brand: #9D78EA;
--color-brand-soft: #2B2437;
--color-on-brand: #111318;
--color-success: #53C89A;
--color-warning: #F2B84D;
--color-error: #FF7A88;
```

Rules:
- neutral interface + один фирменный violet;
- нет отдельных декоративных цветов для Chat/Image/Video/Audio/3D/SVG;
- только primary/secondary text levels;
- success/warning/error используются только как системные состояния;
- hover/focus/selected выводятся через semantic tokens и `color-mix`; новые HEX в component CSS не создаются;
- logo gradient допустим только внутри logo asset;
- generated content не ограничивается UI palette;
- compatibility aliases старых CSS-переменных разрешены только как migration layer и должны ссылаться на `--color-*`.

## 4. Registration / guest

- Обычная регистрация открытая; invite остаётся operator/test режимом.
- Login/Register не содержат package IDs и технических стадий.
- Guest image trial использует только server-owned guest budget; frontend не создаёт локальный wallet/success.
- После регистрации пользователь возвращается в продукт, по умолчанию в Chat.

## 5. Feed / Gallery

- Feed доступен без login и остаётся визуальным Explore.
- До FEED backend разрешены только явно presentation-примеры; нельзя имитировать реальных authors/likes/publications.
- Gallery показывает только server-owned private assets текущего пользователя.
- Download/preview ownership и bytes validation остаются backend/Media responsibility.

## 6. Account / tokens

- UI не выдумывает daily/monthly buckets, если их нет в backend contract.
- До появления отдельного billing bucket в shell используется нейтральное действие `Токены`/`Баланс` с переходом к server Credits.
- Admin links не видны без staff permissions.

## 7. Responsive contract

Обязательные CSS viewport checks: 360×800, 390×844, 768×1024, 1024×768, 1440×900, 1920×1080,
2560×1440, 3840×2160 и 7680×4320. Дополнительно DPR=2/1.5 и ручная Windows scaling 125/150/200%.

8K не растягивает reading text на весь экран: Chat/composer остаются bounded, а Feed/Gallery/Canvas/Table используют ширину.
На телефоне нет document horizontal overflow; primary actions доступны без hover.

## 8. Frontend acceptance

- `/` и `/studio/chat` показывают Chat home;
- `/feed` остаётся отдельным Explore;
- top creative nav: Chat/Image/Video/Audio/3D;
- mobile: horizontal creative nav + short Chat/Feed/Gallery bottom nav;
- light default + persistent dark switch;
- semantic v1.1 colors одинаковы на всех пользовательских surfaces;
- отсутствуют decorative per-mode colors;
- Chat не показывает fake server success;
- existing Image/Gallery/Account/Admin server contracts не меняются этим visual package;
- no horizontal overflow на полной viewport matrix.
