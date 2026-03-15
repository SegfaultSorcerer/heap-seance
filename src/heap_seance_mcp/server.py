from __future__ import annotations

import os
import sys
from typing import Any

from . import tools

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - runtime dependency
    FastMCP = None  # type: ignore[assignment]


def _must_have_mcp() -> Any:
    if FastMCP is None:
        raise RuntimeError(
            "The 'mcp' package is not installed. Run 'pip install -e .' in this project first."
        )
    return FastMCP


def build_server() -> Any:
    fastmcp = _must_have_mcp()
    mcp = fastmcp("heap-seance")

    @mcp.tool()
    def java_list_processes() -> dict[str, Any]:
        return tools.java_list_processes()

    @mcp.tool()
    def java_gc_snapshot(pid: int, interval_s: int = 2, samples: int = 6) -> dict[str, Any]:
        return tools.java_gc_snapshot(pid=pid, interval_s=interval_s, samples=samples)

    @mcp.tool()
    def java_class_histogram(pid: int, live_only: bool = True) -> dict[str, Any]:
        return tools.java_class_histogram(pid=pid, live_only=live_only)

    @mcp.tool()
    def java_jfr_start(
        pid: int,
        profile: str = "profile",
        duration_s: int = 30,
        out_file: str | None = None,
    ) -> dict[str, Any]:
        return tools.java_jfr_start(
            pid=pid,
            profile=profile,
            duration_s=duration_s,
            out_file=out_file,
        )

    @mcp.tool()
    def java_jfr_summary(jfr_file: str) -> dict[str, Any]:
        return tools.java_jfr_summary(jfr_file=jfr_file)

    @mcp.tool()
    def java_heap_dump(pid: int, live_only: bool = True, out_file: str | None = None) -> dict[str, Any]:
        return tools.java_heap_dump(pid=pid, live_only=live_only, out_file=out_file)

    @mcp.tool()
    def java_mat_suspects(heap_dump_file: str) -> dict[str, Any]:
        return tools.java_mat_suspects(heap_dump_file=heap_dump_file)

    @mcp.tool()
    def java_async_alloc_profile(
        pid: int,
        duration_s: int = 30,
        out_file: str | None = None,
    ) -> dict[str, Any]:
        return tools.java_async_alloc_profile(pid=pid, duration_s=duration_s, out_file=out_file)

    return mcp


def main() -> None:
    try:
        server = build_server()
        transport = os.environ.get("MCP_TRANSPORT", "stdio")
        if transport == "sse":
            server.run(transport="sse")
        else:
            server.run()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to start heap-seance MCP server: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
