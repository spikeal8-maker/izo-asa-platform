# FRONTEND-001 — remaining gate request

Статус: **staging / gate coordination**. Не является owner acceptance и не является independent review evidence.

Exact source under review: `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.
PR: `#36`.

## 1. Уже доказано

- exact-head Foundation CI: success;
- Dependency Security: success;
- Review Source: success;
- browser evidence artifact существует для exact source;
- package self-review recorded;
- source branch остаётся frozen;
- PR остаётся Draft/unmerged.

## 2. Owner visual acceptance — что именно нужно принять

Owner должен посмотреть именно текущий `FRONTEND-001`, а не staging preview будущего Chat change.

Минимальная проверка:

- desktop empty Chat: heading + centered composer;
- mobile Chat: две верхние строки, пять creative modes доступны, bottom Chat/Feed/Gallery;
- 1440/1920/QHD/UHD: header не перегружен, text measure не растянут;
- light/dark semantic color direction приемлема;
- Feed/Gallery/Account/Admin inherited surfaces не выглядят сломанными после shell change;
- текущая кнопка `Инструменты` может быть принята как временный FRONTEND-001 state, потому что её удаление уже вынесено в post-checkpoint reconciliation candidate.

Owner acceptance FRONTEND-001 не означает автоматическое принятие всех UX v4 proposed features/routes.

## 3. Independent review — предмет проверки

Отдельный reviewer должен проверять exact source SHA, а не staging branch.

Review focus:

- scope = 40/40 paths, cross_domain, risk=high;
- no backend business-contract regression;
- Chat does not fake server assistant success;
- Image paid path still uses server quote + stable operation id;
- private Gallery behavior/ownership preserved;
- Account/Admin/Access security-sensitive handlers not weakened;
- CSP change remains only the documented bounded private-image requirement;
- semantic tokens do not introduce per-modality decorative colors;
- responsive tests/evidence correspond to exact source;
- no test/limit weakening used to obtain green CI.

Reviewer must publish the machine-readable PASS evidence required by `tools/review_evidence.py` only after completing the review. Request text itself must never imitate that PASS marker.

## 4. Gate ordering

Recommended order:

1. owner visual acceptance of current exact source;
2. independent reviewer inspects exact source and posts required evidence;
3. re-fetch PR comments and verify marker is bound to `5c0e79b...`;
4. do not modify frozen source afterward;
5. only then attempt lifecycle continuation.

## 5. Newly found continuation blocker

Even after both gates, current `project_state` cannot activate a newly selected `FRONTEND-002` while `next_package=null` and the package is absent from PLAN.

See:

- `LIFECYCLE_NEXT_SELECTION_GAP.md`;
- `PROJECT_STATE_DECIDES_NEXT_PATCH_PREVIEW.md`.

Therefore gate completion alone is necessary but not sufficient for safe continuation. Do not work around the tooling defect by editing PLAN on the frozen branch.

## 6. Self-review

PASS as coordination document:

- does not claim owner acceptance;
- does not claim independent review;
- does not contain a fake PR PASS marker;
- exact source remains the only review target;
- continuation tooling gap is disclosed rather than bypassed.
