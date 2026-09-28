# Протокол fusion-cad-ai

## Конверт

Каждый вызов Fusion — один скрипт официального `fusion_mcp_execute`. Сервер встраивает JSON операции внутрь скрипта, не склеивает код пользователя со строками Python.

```text
def run(_context: str):
    ... загрузить fusion_runtime/loader.py ...
    runtime.handle(op, params_json, request_id)
```

Успех печатает одну строку `FCA>>{...}<<FCA`. Ошибка поднимает `RuntimeError` с тем же маркером в тексте: официальный MCP при исключении не отдаёт stdout. Клиент берёт последнюю пару маркеров из сообщения или из traceback.

Поля конверта: `v` (сейчас 1), `id`, `op`, `params`, `root`, `sha`. `sha` — хеш исходников `fca_rt`. Если он совпал с уже загруженным runtime, состояние сессии сохраняется. Если нет, runtime перезагружается, а словарь состояния переносится.

Большой ответ пишется в `.runtime/results/<id>.json`, а в конверте остаётся ссылка.

## Транспорты

`OfficialMcpTransport` говорит с `127.0.0.1:27182` сырым сокетом: заголовок `Expect: 100-continue`, тело после `HTTP/1.1 100 Continue`, `Connection: close`. Сессия MCP передаётся заголовком `Mcp-Session-Id`.

`FakeTransport` считает коробки, цилиндры и отверстия аналитически и используется в pytest без Fusion.

`BridgeTransport` — запасной канал. Клиент читает `.runtime/bridge.json`. Аддин, который пишет этот файл, в репозиторий не входит: spike официального MCP прошёл, и ADR-001 оставил мост только как клиент.

## Песочница

Код `execute` проверяется по AST до запуска и ещё раз внутри Fusion. Разрешены `adsk`, `math`, `json`, `re`, `dataclasses`, `typing`, `itertools`, `functools`, `collections` и пакет `fca_rt`. Запрещены `os`, `sys`, `pathlib`, `subprocess`, `socket`, `open`, `eval`, `exec`.

## Подтверждения

`reset`, открытие чужого облачного документа, сохранение в облако и создание чертежа требуют `confirm=true`. Удаления проектов и документов нет.
