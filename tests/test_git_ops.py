"""Tests for Git Version Control Tool — Prompt Spec §2, §3, §4."""

import pytest
from tools.git_tool import GitOpsTool


@pytest.mark.asyncio
async def test_git_ops_tool_status_and_branch():
    tool = GitOpsTool()

    # Status check
    res_status = await tool.execute({"subcommand": "status"})
    assert res_status.success is True
    assert "stdout" in res_status.output

    # List branches
    res_branch = await tool.execute({"subcommand": "branch"})
    assert res_branch.success is True
    assert "main" in res_branch.output["stdout"]
