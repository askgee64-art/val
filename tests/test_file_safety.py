"""Tests for File Safety Architecture — Document 35 & Master Spec §12."""

import pytest
from pathlib import Path
from val.security.file_safety import FileSafetyGuard


def test_file_safety_escape_prevention():
    guard = FileSafetyGuard()
    # Path traversal ../../etc/passwd should not escape workspace
    decision = guard.check("read", "../../../../etc/passwd", base="workspace")
    # Resolve re-roots or blocks relative-to checks
    if decision.allowed:
        # Check that resolved path is strictly inside workspace
        assert Path(decision.resolved_path).is_relative_to(guard.workspace)


def test_file_safety_protected_path_mutation_denied():
    guard = FileSafetyGuard()
    # Attempting to overwrite core VAL backend
    decision = guard.check("write", "/home/user/val/backend/val/config.py", base="workspace")
    assert decision.allowed is False
    assert decision.is_protected is True or "denied" in decision.reason


def test_file_safety_allowed_workspace_write():
    guard = FileSafetyGuard()
    decision = guard.check("write", "output.txt", base="workspace")
    assert decision.allowed is True
    assert decision.is_protected is False
    assert Path(decision.resolved_path).is_relative_to(guard.workspace)


def test_file_safety_chmod_denied():
    guard = FileSafetyGuard()
    decision = guard.check("chmod", "script.sh", base="workspace")
    assert decision.allowed is False
    assert "chmod_denied" in decision.reason
