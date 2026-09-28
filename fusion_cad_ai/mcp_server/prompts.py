"""Session prompt."""

from __future__ import annotations


def register(server) -> None:
    @server.prompt(name="start-cad-session", description="Как начать моделирование в fusion-cad-ai.")
    def start_cad_session() -> str:
        return (
            "Работай через fusion-cad-ai. Официальный fusion_mcp_execute — только readOnly. "
            "Цикл: BUILD, VALIDATE, INSPECT, PREVIEW, проверочный экспорт, VERIFY, затем exports/. "
            "Размеры с единицами, имена *_mm. Документы только FCA_. STEP — мастер. "
            "Не закрывай и не сохраняй чужие документы."
        )
