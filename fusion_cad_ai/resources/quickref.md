# Краткая шпаргалка

1. `new_design` — документ `FCA_<имя>`, параметрический, гибрид, миллиметры.
2. `execute` или `execute_file` — геометрия. Хелперы: `make_box_mm`, `mm(value, "mm")`, `show`, `measure`.
3. `validate`, затем `inspect_part`, затем `render_view`.
4. `export` пишет черновик в `.runtime/verify` и копирует в `exports/` только после проверки.
5. STEP — мастер. STL и 3MF — для печати.
6. Чужой документ не активируется, не сохраняется и не закрывается.
