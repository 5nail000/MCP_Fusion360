# MCP_Fusion360

Среда Cursor → MCP → Autodesk Fusion. Агент задаёт параметры в миллиметрах, сервер `fusion-cad-ai` собирает деталь в живом Fusion, проверяет её и только потом копирует STEP, STL, 3MF и F3D в `exports/`.

## Два сервера

`.cursor/mcp.json` поднимает оба:

- `fusion-official` — официальный MCP Fusion на `http://127.0.0.1:27182/mcp`;
- `fusion-cad-ai` — этот репозиторий, stdio через `tools/run-fusion-cad-ai.cmd`.

По умолчанию агент видит 33 инструмента групп `core` и `assembly`. CAM, листовой металл, рендер, объёмные решётки, конфигурации, чертежи и облако включаются переменной `FCA_TOOL_GROUPS`.

## Цикл

`BUILD → VALIDATE → INSPECT → preview → временный файл в .runtime/verify → VERIFY → exports/`.

STEP — мастер. STL и 3MF — сетки для печати. Принтеры по умолчанию: Bambu Lab A1 (256 мм, сопло 0.4) и A1 mini (180 мм, сопло 0.4).

## Модели

| Файл | Что это |
| --- | --- |
| `models/parts/flange.py` | фланец Ø40, 4 отверстия по окружности |
| `models/parts/enclosure.py` | корпус 80×40×25, открытый верх |
| `models/parts/print_bracket.py` | кронштейн под печать |
| `models/parts/plate_e2e.py` | пластина 60×40×6 с двумя Ø5 |
| `models/assemblies/pin_joint.py` | палец и крышка, зазор 0.2 мм |
| `models/assemblies/motion_stop.py` | рычаг и упор |

```powershell
uv run python scripts/run_pipeline.py plate_e2e
uv run pytest
uv run pytest -m fusion
```

Второй набор тестов требует запущенный Fusion. Окно не сворачивай и не закрывай уже открытые документы: сервер создаёт только `FCA_<имя>`.

## Лицензия кода

MIT. Ограничения лицензии Fusion описаны в `docs/license-limits.md` и читаются с живого API, а не зашиваются в код.
