# ADR-008. Профили инструментов

Статус: принято 2026-09-28.

Жёсткого лимита Cursor больше нет (Dynamic Context Discovery), практический бюджет — около 40 активных инструментов на все серверы.

`FCA_TOOL_GROUPS` по умолчанию `core,assembly`: 29 инструментов ядра + 4 сборочных. Вместе с 4 инструментами официального MCP это 37.

Остальные группы выключены, пока их не перечислят в переменной: `library`, `refs`, `cam`, `sheet_metal`, `render`, `volume`, `configs`, `drawings`, `cloud`, `experimental`.

`FCA_TOOLS` — точный allowlist имён. Если задан, группы игнорируются.

Аннотации MCP: `readOnlyHint`, `destructiveHint`, `idempotentHint`. Их снимок проверяет `tests/contract/test_tool_surface.py`.
