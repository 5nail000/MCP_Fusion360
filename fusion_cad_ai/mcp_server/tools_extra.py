"""CAM, sheet metal, render, volume, configurations, drawings, cloud."""

from __future__ import annotations

from fusion_cad_ai import service
from fusion_cad_ai.mcp_server.tools_core import DESTR, MUT, RO

CAM = [
    ("cam_setup", service.cam_setup, MUT, "CAM-сетап из шаблона. Есть предупреждение о лимитах лицензии."),
    ("cam_generate", service.cam_generate, MUT, "Траектории как job. Дальше job_status."),
    ("cam_post", service.cam_post, MUT, "Постпроцессор в exports/nc."),
    ("cam_recognize", service.cam_recognize, RO, "Отверстия и карманы."),
]
SHEET = [
    ("sheet_metal_rules", service.sheet_metal_rules, RO, "Правила листового металла документа."),
    ("sheet_metal_flat_pattern", service.sheet_metal_flat_pattern, MUT, "Развёртка в DXF, exports/dxf."),
]
RENDER = [
    ("render_photo", service.render_photo, MUT, "Локальный рендер как job, файл в renders/."),
]
VOLUME = [
    ("volumetric_apply", service.volumetric_apply, MUT, "Объёмная модель и решётка BeamNetwork, если билд её принимает."),
]
CONFIGS = [
    ("config_get", service.config_get, RO, "Строки таблицы конфигураций."),
    ("config_set", service.config_set, MUT, "Активировать строку конфигурации."),
]
DRAWINGS = [
    ("drawing_export", service.drawing_export, MUT, "Чертёж Fusion или SVG, если нет сохранённого DataFile."),
    ("visual_analyses", service.visual_note, RO, "Какие визуальные анализы есть в этом билде."),
]
CLOUD = [
    ("cloud_list", service.cloud_list, RO, "Проекты хаба. Ничего не удаляет."),
    ("cloud_open", service.cloud_open, MUT, "Открыть облачный файл. Нужен confirm=true."),
    ("cloud_save", service.cloud_save, DESTR, "Сохранить FCA-документ в MCP_Fusion360_Sandbox. Нужен confirm=true."),
]
