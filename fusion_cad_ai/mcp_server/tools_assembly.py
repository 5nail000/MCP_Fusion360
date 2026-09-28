"""Assembly tools."""

from __future__ import annotations

from fusion_cad_ai import service
from fusion_cad_ai.mcp_server.tools_core import MUT, RO

ASSEMBLY = [
    ("assembly_add_part", service.assembly_add_part, MUT, "Компонент сборки и, если задан source, модель из models/."),
    ("joint_create", service.joint_create, MUT, "Шарнир rigid, revolute, slider, cylindrical, pin-slot, planar или ball."),
    ("interference", service.interference, RO, "Пересечения тел. Пустой список — все тела документа."),
    ("motion_sweep", service.motion_sweep, MUT, "Прогон шарнира по углу. В конце положение возвращается."),
]
