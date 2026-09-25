"""Tests for Tool System and Safe Builtins — Document 12."""

import pytest
from val.tools.builtins import (
    CodeSandboxTool,
    EchoTool,
    FileListTool,
    FileReadTool,
    FileWriteTool,
    SafeCalculatorTool,
    SystemInfoTool,
)


@pytest.mark.asyncio
async def test_echo_tool():
    tool = EchoTool()
    res = await tool.execute({"message": "ping"})
    assert res.success is True
    assert res.output == {"echo": "ping"}


@pytest.mark.asyncio
async def test_calculator_tool_valid():
    tool = SafeCalculatorTool()
    res = await tool.execute({"expression": "2 * (3 + 4) / 2"})
    assert res.success is True
    assert res.output["result"] == 7.0

    res_sqrt = await tool.execute({"expression": "sqrt(16) + 5"})
    assert res_sqrt.success is True
    assert res_sqrt.output["result"] == 9.0


@pytest.mark.asyncio
async def test_calculator_tool_rejection():
    tool = SafeCalculatorTool()
    # Arbitrary code execution attempt via __import__
    res = await tool.execute({"expression": "__import__('os').system('ls')"})
    assert res.success is False
    assert "error" in res.error.lower()


@pytest.mark.asyncio
async def test_system_info_probe():
    tool = SystemInfoTool()
    res = await tool.execute({})
    assert res.success is True
    data = res.output
    assert "cpu_cores" in data
    assert "ram_total_mb" in data
    assert "disk_free_gb" in data
    assert "classification" in data


@pytest.mark.asyncio
async def test_code_sandbox_success():
    tool = CodeSandboxTool()
    code = "import math\nprint('Computed:', math.factorial(5))"
    res = await tool.execute({"code": code, "timeout_seconds": 5})
    assert res.success is True
    assert "Computed: 120" in res.output["stdout"]
    assert res.output["exit_code"] == 0


@pytest.mark.asyncio
async def test_code_sandbox_timeout():
    tool = CodeSandboxTool()
    code = "import time\ntime.sleep(10)\nprint('done')"
    res = await tool.execute({"code": code, "timeout_seconds": 1})
    assert res.success is False
    assert "timed_out" in res.error.lower()


@pytest.mark.asyncio
async def test_file_tools_roundtrip():
    write_tool = FileWriteTool()
    read_tool = FileReadTool()
    list_tool = FileListTool()

    # Write
    w_res = await write_tool.execute(
        {"path": "test_note.txt", "content": "Hello from VAL safe file tool!"}
    )
    assert w_res.success is True

    # Read
    r_res = await read_tool.execute({"path": "test_note.txt"})
    assert r_res.success is True
    assert "Hello from VAL safe file tool!" in r_res.output["content"]

    # List
    l_res = await list_tool.execute({"path": "."})
    assert l_res.success is True
    names = [f["name"] for f in l_res.output["entries"]]
    assert "test_note.txt" in names
