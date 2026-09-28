# ADR-006. Снимки

Статус: принято 2026-09-28.

`save_snapshot` сохраняет в сессии `fca_rt`:

- выражения user parameters (имя → expression);
- `timeline.markerPosition` и список suppress;
- реестр имён (`show`) как entityToken;
- метрики `measure` на момент снимка.

Геометрия не копируется в STEP на каждый снимок: откат — это возврат выражений и маркера таймлайна. Временный STEP пишется только если вызвали `save_snapshot` с `include_brep=true` (файл в `.runtime/snapshots/`).

`restore_snapshot` возвращает параметры и маркер, затем сравнивает объём с сохранённой метрикой. Расхождение больше 0.2 % попадает в `warnings`.

`execute_file` перед запуском сам делает снимок `fca_auto_before_file` и при ошибке откатывается на него.

`design_audit` и `motion_sweep` тоже обязаны восстановить состояние, даже если проверка упала.
