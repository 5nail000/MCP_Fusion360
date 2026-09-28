# ADR-007. Второе ядро проверки

Статус: принято 2026-09-28.

Группа зависимостей `verify` (не ставится обычным `uv sync`, только `uv sync --group verify`):

- `build123d==0.11.1` (тянет OpenCascade);
- `augura==0.1.7`;
- `trimesh==5.1.0`;
- `lib3mf==2.5.0`, если резолвится; иначе 3MF проверяется как zip.

Проверочный экспорт пишется в `.runtime/verify/`. Финальные файлы в `exports/` копируются только после PASS.

Проверки:

- STEP: размер, заголовок ISO-10303, затем объём и bbox через build123d/OCP, допуск объёма ±0.2 % и bbox ±0.02 мм относительно `measure` Fusion;
- STL: непустой, watertight через trimesh, если модуль есть;
- 3MF: zip-сигнатура `PK` и `[Content_Types].xml`;
- `validate(deep=true)` и `cross_sections` используют тот же STEP.

Нет группы `verify` — инструменты возвращают `warnings: ["verify group not installed"]` и не называют это PASS глубокой проверки. Геометрический gate Fusion (health таймлайна, solid, объём) при этом считается.

Паритет с MCP_FreeCAD: `tests/golden/parity_freecad.json`, допуск тот же. Репозиторий MCP_FreeCAD только читается.
