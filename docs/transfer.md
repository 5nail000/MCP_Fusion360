# Перенос

Репозиторий не хранит путь к профилю пользователя и не хранит токены.

- Python-зависимости ставятся через `uv sync` по `uv.lock`.
- Путь к Fusion ищется в `%LOCALAPPDATA%\Autodesk\webdeploy\production\*\Fusion360.exe` скриптом `scripts/find_fusion.ps1`.
- Заглушки API лежат в `%APPDATA%\Autodesk\Autodesk Fusion 360\API\Python\defs`. Их подключает `scripts/setup_ide.ps1` только на этой машине.
- `.runtime/`, `logs/`, `.venv/` и `exports/*` кроме `.gitkeep` не коммитятся.
- После обновления Fusion запусти `scripts/discover_official_tools.py`. Если набор официальных инструментов изменился, `health_check` вернёт `CONTRACT_CHANGED` относительно `docs/official-fusion-mcp/*.json`.
- `scripts/precommit_check.ps1` отклоняет имя каталога профиля, абсолютный путь к профилю Windows, префикс токена GitHub и адрес почты.
