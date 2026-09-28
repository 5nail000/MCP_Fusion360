"""Core tool table: 29 tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

from fusion_cad_ai import service

RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
MUT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
IDEM = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True)
DESTR = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)

CORE = [
    ("health_check", service.health_check, RO, "Связь с Fusion, лицензия, билд и хеш runtime."),
    ("version", service.version, RO, "Версия пакета fusion-cad-ai и конверта."),
    ("workflow_hints", service.workflow_hints, RO, "Цикл BUILD → VERIFY и правила единиц."),
    ("session_state", service.session_state, RO, "Активный FCA-документ, тела и пространство execute."),
    ("new_design", service.new_design, MUT, "Документ FCA_<имя>, Parametric, Hybrid, миллиметры."),
    ("reset", service.reset, DESTR, "Очищает таймлайн только FCA-документа. Нужен confirm=true."),
    ("job_status", service.job_status, RO, "Состояние долгой задачи CAM или рендера."),
    ("execute", service.execute, MUT, "Python в песочнице Fusion. Хелперы: make_box_mm, mm, show, measure."),
    ("execute_file", service.execute_file, MUT, "Собрать models/*.py. При ошибке откатывает снимок."),
    ("script", service.script, RO, "Журнал выполненных блоков execute."),
    ("last_error", service.last_error, RO, "Последняя ошибка runtime и Application.getLastError."),
    ("repair_hints", service.repair_hints, RO, "Подсказка по тексту ошибки Fusion."),
    ("params_get", service.params_get, RO, "User parameters и diff с dataclass модели."),
    ("params_set", service.params_set, IDEM, "Меняет параметры. Каждое значение — {value, unit}."),
    ("save_snapshot", service.save_snapshot, IDEM, "Снимок выражений, маркера таймлайна и метрик."),
    ("restore_snapshot", service.restore_snapshot, IDEM, "Откат к снимку."),
    ("measure", service.measure, RO, "Объём мм³, bbox мм, площадь мм², масса г."),
    ("validate", service.validate, RO, "Здоровье таймлайна, solid, объём. deep проверяет STEP."),
    ("locate_defects", service.locate_defects, RO, "Ошибки таймлайна."),
    ("inspect_part", service.inspect_part, RO, "Сверка с expected_json: PASS или FAIL."),
    ("cross_sections", service.cross_sections, RO, "Площади сечений вдоль оси."),
    ("compare", service.compare, RO, "Сравнение shape, fit, align или snapshot."),
    ("design_audit", service.design_audit, MUT, "Шевелит параметры на ±ε и откатывает."),
    ("analyze_printability", service.analyze_printability, RO, "Влезает ли деталь в Bambu A1 или A1 mini."),
    ("find_features", service.find_features, RO, "Отверстия и окружности болтов."),
    ("resolve", service.resolve, IDEM, "Селектор, атрибут и entityToken."),
    ("render_view", service.render_view, RO, "PNG в renders/ и base64 в ответе."),
    ("export", service.export, IDEM, "Проверочный файл, затем копия в exports/. STEP — мастер."),
    ("import_cad_file", service.import_cad_file, MUT, "STEP, F3D, SMT или сетка в активный FCA-документ."),
]
