# ADR-003. Транспорт и безопасность

Статус: принято 2026-09-28.

## Официальный MCP

Сервер без аутентификации на loopback. Его включает человек на время работы и выключает после. Правило продублировано в `AGENTS.md`.

Клиент (`fusion_cad_ai/transport/official_mcp.py`):

- `Expect: 100-continue`, затем тело;
- `Connection: close` (у сервера `Keep-Alive: max=5`);
- мутирующий вызов сначала читает `activeCommand` и при открытом диалоге возвращает `COMMAND_DIALOG_OPEN`;
- `fusion_mcp_execute` со стороны агента разрешён только с `readOnly: true`. Сохранение и закрытие документов — только инструменты `cloud_*` с `confirm=true`.

## Песочница execute

Проверка AST дважды: в сервере и в `fca_rt/sandbox.py`. Разрешённые корни импорта: `adsk`, `math`, `json`, `re`, `dataclasses`, `typing`, `itertools`, `functools`, `collections`, `fca_rt`. Запрещены `open`, `eval`, `exec`, `compile`, `__import__` вне allowlist, `os`, `sys`, `pathlib`, `subprocess`, `socket`, `shutil`.

Запись файлов из рантайма — только в `exports/`, `renders/`, `.runtime/`.

## Мост

Если когда-нибудь понадобится (ADR-001): только `127.0.0.1`, случайный порт, токен в `.runtime/bridge.json`, тело запроса до 8 МБ, ответ до 32 МБ. Протокол — `docs/protocol.md`. Add-in в этом релизе нет.
