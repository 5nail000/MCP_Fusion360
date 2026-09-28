# Установка

1. Установи [uv](https://docs.astral.sh/uv/) в `%USERPROFILE%\.local\bin`.
2. Открой Autodesk Fusion и включи официальный MCP: `http://127.0.0.1:27182/mcp`.
3. В каталоге репозитория выполни `uv sync`.
4. Проверь `uv run fusion-cad-ai --version`.
5. `uv run python scripts/collect_versions.py` обновляет `docs/versions.lock`.
6. `powershell -File scripts/setup_ide.ps1` пишет локальный `.vscode/settings.json` с путём к заглушкам `adsk`. Файл в git не входит.
7. `powershell -File scripts/compile_fusion_side.ps1` компилирует `fusion_runtime` и `models` интерпретатором Python 3.14, тем же мажорным, что у Fusion.
8. Cursor читает `.cursor/mcp.json`: HTTP-сервер `fusion-official` и stdio-сервер `fusion-cad-ai` через `tools/run-fusion-cad-ai.cmd`.

Окно Fusion не сворачивай, если нужен снимок. Свёрнутое окно не попадает в `saveAsImageFile`.

Глубокая проверка STEP ставится отдельно: `uv sync --group verify`. Без неё пайплайн пишет предупреждение и всё равно проверяет, что STEP начинается с `ISO-10303-21`, а STL и 3MF — валидные контейнеры.
