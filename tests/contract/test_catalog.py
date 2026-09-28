from __future__ import annotations

import asyncio

from fusion_cad_ai.mcp_server.server import GROUPS, build_server

CORE = {
    "health_check",
    "version",
    "workflow_hints",
    "session_state",
    "new_design",
    "reset",
    "job_status",
    "execute",
    "execute_file",
    "script",
    "last_error",
    "repair_hints",
    "params_get",
    "params_set",
    "save_snapshot",
    "restore_snapshot",
    "measure",
    "validate",
    "locate_defects",
    "inspect_part",
    "cross_sections",
    "compare",
    "design_audit",
    "analyze_printability",
    "find_features",
    "resolve",
    "render_view",
    "export",
    "import_cad_file",
}
ASSEMBLY = {"assembly_add_part", "joint_create", "interference", "motion_sweep"}


def test_default_profile_is_core_and_assembly() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == CORE | ASSEMBLY
    readonly = {tool.name for tool in tools if tool.annotations and tool.annotations.read_only_hint}
    assert "measure" in readonly
    assert "execute" not in readonly
    assert "reset" in {tool.name for tool in tools if tool.annotations and tool.annotations.destructive_hint}


def test_optional_groups_exist() -> None:
    assert set(GROUPS) >= {
        "core",
        "assembly",
        "library",
        "refs",
        "cam",
        "sheet_metal",
        "render",
        "volume",
        "configs",
        "drawings",
        "cloud",
        "experimental",
    }


def test_prompt_and_resources_registered() -> None:
    server = build_server()
    prompts = asyncio.run(server.list_prompts())
    resources = asyncio.run(server.list_resources())
    assert any(item.name == "start-cad-session" for item in prompts)
    uris = {str(item.uri) for item in resources}
    assert "fca://quickref" in uris
    assert "fca://printers" in uris
    assert "fca://skills/modeling" in uris
