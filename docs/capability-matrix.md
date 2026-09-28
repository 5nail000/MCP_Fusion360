# Матрица возможностей

Группы по умолчанию: `core` и `assembly` (33 инструмента). Остальные включаются `FCA_TOOL_GROUPS`.

| Группа | Инструменты | Статус |
| --- | --- | --- |
| core | new_design, execute, execute_file, measure, validate, locate_defects, inspect_part, cross_sections, compare, render_view, export, import_file, params_get, params_set, save_snapshot, restore_snapshot, health_check, session_state, reset, last_error, script_log, job_status, repair_hints, list_parameters | проверено на кубе и эталонных моделях |
| assembly | assembly_add, joint_create, motion_sweep, interference | revolute, слайдер и остальные типы; натяг ловится analyzeInterference |
| library | search_library, load_part | модели в `models/lib` и типы резьб ThreadDataQuery |
| refs | prepare_drawing, crop_drawing | Pillow, локальные PNG |
| cam | cam_setup, cam_generate, cam_post, cam_recognize | шаблон, future и пост; предупреждение Personal Use. FFF Bambu — research, пост не подделывается |
| sheet_metal | sheet_rules, sheet_flat | развёртка только у листового тела, DXF в `exports/dxf` |
| render | render_photo | локальный рендер как job |
| volume | volumetric_lattice | граф `adsk.volume`, если тип узла есть в этой сборке Fusion |
| configs | config_get, config_set | таблица конфигураций; пустая таблица сообщается честно |
| drawings | drawing_export, visual_analyses | чертёж Fusion после confirm, иначе SVG-запасной путь |
| cloud | cloud_list, cloud_open, cloud_save | проект-песочница, без удалений |
| experimental | verify_spec, suggest_spec | сверка bbox и объёма со спецификацией |

Официальные `fusion_mcp_read`, `fusion_mcp_execute`, `fusion_mcp_update`, `fusion_mcp_electronics_read` остаются отдельным MCP-сервером `fusion-official`.
