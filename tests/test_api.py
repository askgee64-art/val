"""API integration tests for VAL — Document 22 & Master Spec §4."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from val.api.app import app
from val.config import get_settings
from val.db.session import init_db


@pytest_asyncio.fixture(autouse=True)
async def init_test_database():
    await init_db()


@pytest.fixture
def auth_headers():
    settings = get_settings()
    return {
        "x-val-founder-key": settings.founder_token,
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_api_status_and_diagnostics(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/status", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["app_name"] == "VAL"
        assert data["database_ok"] is True
        assert data["tools_registered"] >= 7
        assert data["founder_authenticated"] is True

        diag_res = await client.get("/api/v1/diagnostics", headers=auth_headers)
        assert diag_res.status_code == 200
        diag = diag_res.json()
        assert "cpu_cores" in diag
        assert "ram_total_mb" in diag


@pytest.mark.asyncio
async def test_api_chat_and_task_execution(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit math objective
        payload = {
            "content": "Calculate the square root of 256 and multiply by 4",
            "auto_execute": True,
        }
        res = await client.post("/api/v1/chat", json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("succeeded", "running")
        assert "task" in data
        assert "message" in data
        assert data["plan"] is not None

        task_id = data["task"]["task_id"]

        # Verify task via /tasks/{id}
        task_res = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
        assert task_res.status_code == 200
        t = task_res.json()
        assert t["task_id"] == task_id


@pytest.mark.asyncio
async def test_api_tool_execution(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List tools
        tools_res = await client.get("/api/v1/tools", headers=auth_headers)
        assert tools_res.status_code == 200
        tools = tools_res.json()
        assert any(t["name"] == "calculator" for t in tools)

        # Execute safe tool directly
        exec_res = await client.post(
            "/api/v1/tools/calculator/execute",
            json={"expression": "100 / 4"},
            headers=auth_headers,
        )
        assert exec_res.status_code == 200
        result = exec_res.json()
        assert result["success"] is True
        assert result["output"]["result"] == 25.0


@pytest.mark.asyncio
async def test_api_memory_lifecycle(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Store
        store_res = await client.post(
            "/api/v1/memory",
            json={
                "scope_type": "working",
                "key": "test_pref",
                "content": {"theme": "cyber_dark", "priority": "high"},
                "importance": 0.8,
            },
            headers=auth_headers,
        )
        assert store_res.status_code == 200

        # Recall
        recall_res = await client.get("/api/v1/memory?key=test_pref", headers=auth_headers)
        assert recall_res.status_code == 200
        records = recall_res.json()
        assert len(records) >= 1
        assert records[0]["content"]["theme"] == "cyber_dark"


@pytest.mark.asyncio
async def test_api_audit_log_query(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        audit_res = await client.get("/api/v1/audit?limit=10", headers=auth_headers)
        assert audit_res.status_code == 200
        logs = audit_res.json()
        assert isinstance(logs, list)


@pytest.mark.asyncio
async def test_api_emergency_control_plane(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Pause
        pause_res = await client.post("/api/v1/control/pause", headers=auth_headers)
        assert pause_res.status_code == 200
        assert pause_res.json()["global_paused"] is True

        # 2. Resume
        resume_res = await client.post("/api/v1/control/resume", headers=auth_headers)
        assert resume_res.status_code == 200
        assert resume_res.json()["global_paused"] is False

        # 3. Emergency stop
        emg_res = await client.post("/api/v1/control/emergency", headers=auth_headers)
        assert emg_res.status_code == 200
        assert emg_res.json()["emergency"] is True

        # 4. Clear emergency
        clear_res = await client.post("/api/v1/control/emergency/clear", headers=auth_headers)
        assert clear_res.status_code == 200
        assert clear_res.json()["emergency"] is False
