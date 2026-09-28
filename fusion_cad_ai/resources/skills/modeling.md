# Моделирование

Один файл `models/parts/<имя>.py` служит и CLI, и MCP. Внутри `build(ctx, params)` нет импорта `adsk`: его вызывает runtime Fusion.

Параметры — dataclass с суффиксами `_mm` и полем `unit = "mm"`. `ctx.params_from` создаёт user parameters, а размеры фич ссылаются на выражения вроде `height_mm`.
