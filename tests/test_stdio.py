"""End to end over the real MCP stdio transport, in a subprocess."""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def run_session(tmp_path, steps):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env["CLASSROOM_MCP_CONFIG_DIR"] = str(tmp_path / "config")
    params = StdioServerParameters(command=sys.executable, args=["-m", "classroom_mcp"], env=env)

    async def go():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await steps(session)

    return asyncio.run(asyncio.wait_for(go(), timeout=60))


def test_server_starts_without_signing_in_and_lists_tools(tmp_path):
    async def steps(session):
        return await session.list_tools()

    result = run_session(tmp_path, steps)
    assert {t.name for t in result.tools} == {
        "get_all_courses",
        "get_assessment_items",
        "read_stream_announcements",
    }
    assert not (tmp_path / "config" / "token.json").exists()


def test_non_ascii_output_survives_the_transport(tmp_path):
    # ADR-005: with the console codepage on stdout this used to kill the process.
    # An unknown tool name is echoed back in the error, which needs no Google call.
    async def steps(session):
        failed = await session.call_tool("café → \U0001f4da", {})
        still_alive = await session.call_tool("get_assessment_items", {"course_id": ""})
        return failed, still_alive

    failed, still_alive = run_session(tmp_path, steps)
    assert failed.isError
    assert "café → \U0001f4da" in failed.content[0].text
    assert still_alive.content[0].text == "Error: course_id is required."
