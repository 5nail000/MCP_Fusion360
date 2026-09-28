# Селекторы

`resolve(object_name, selector, label)` пишет атрибут `fca.<label>` и возвращает `entity_token`.

Токены нельзя сравнивать как строки: один и тот же объект со временем получает другой текст токена. Ищите объект через `findEntityByToken`.

Имена тел задаёт `show(entity, name)`: `flange`, `Part_001_base`, `Part_002_cap`.
