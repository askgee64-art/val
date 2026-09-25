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


@pytest.mark.asyncio
async def test_api_founder_status_and_frontend_serving(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check status contains founder display name
        status_res = await client.get("/api/v1/status", headers=auth_headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["founder_display_name"] == "Tomiwa"

        # Check frontend index serving
        index_res = await client.get("/")
        assert index_res.status_code == 200
        assert "Autonomous AI Personal Operating System" in index_res.text
        assert "Tomiwa" in index_res.text

        # Check styles.css
        css_res = await client.get("/styles.css")
        assert css_res.status_code == 200
        assert "--glass-card" in css_res.text

        # Check app.js
        js_res = await client.get("/app.js")
        assert js_res.status_code == 200
        assert "refreshSystemStatus" in js_res.text


@pytest.mark.asyncio
async def test_api_activity_stream(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/activity?limit=5", headers=auth_headers)
        assert res.status_code == 200
        activities = res.json()
        assert isinstance(activities, list)
        for act in activities:
            assert "id" in act
            assert "title" in act
            assert "timestamp" in act


@pytest.mark.asyncio
async def test_conversational_chat_responses(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Greeting
        res1 = await client.post(
            "/api/v1/chat",
            json={"content": "Hello VAL"},
            headers=auth_headers,
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert "Tomiwa" in data1["message"]["content"]
        assert "VAL" in data1["message"]["content"]
        conv_id = data1["conversation_id"]

        # 2. Active agents inquiry
        res2 = await client.post(
            "/api/v1/chat",
            json={"content": "What agents are currently active?", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert "CALCULUS.VAL" in data2["message"]["content"] or "specialized agents" in data2["message"]["content"]

        # 3. Math calculation
        res3 = await client.post(
            "/api/v1/chat",
            json={"content": "What is 125 × 8?", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert res3.status_code == 200
        data3 = res3.json()
        assert "1,000" in data3["message"]["content"] or "1000" in data3["message"]["content"]

        # 4. Status inquiry
        res4 = await client.post(
            "/api/v1/chat",
            json={"content": "What are you currently working on?", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert res4.status_code == 200
        data4 = res4.json()
        assert "Tomiwa" in data4["message"]["content"] or "working" in data4["message"]["content"]

        # 5. Verify conversation persistence
        convs_res = await client.get("/api/v1/chat/conversations", headers=auth_headers)
        assert convs_res.status_code == 200
        convs = convs_res.json()
        assert any(c["conversation_id"] == conv_id for c in convs)

        msgs_res = await client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=auth_headers)
        assert msgs_res.status_code == 200
        msgs = msgs_res.json()
        assert len(msgs) >= 8  # 4 user + 4 assistant msgs


@pytest.mark.asyncio
async def test_cognitive_engine_acceptance_pipeline(auth_headers):
    """Verifies all cognitive requirements from Founder Directive §22."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # TEST A — Casual conversation ("Hi") must NOT trigger Planner/Task
        res_a = await client.post("/api/v1/chat", json={"content": "Hi"}, headers=auth_headers)
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["task"] is None
        assert data_a["plan"] is None
        assert data_a["message"]["metadata"]["intent"] == "CONVERSATION"
        conv_id = data_a["conversation_id"]

        # TEST B — Personality/Feelings ("What are you feeling like today?") must NOT trigger Planner
        res_b = await client.post(
            "/api/v1/chat",
            json={"content": "What are you feeling like today?", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["task"] is None
        assert data_b["plan"] is None
        assert data_b["message"]["metadata"]["intent"] == "CONVERSATION"

        # TEST C — Context Query ("What were we talking about?")
        res_c = await client.post(
            "/api/v1/chat",
            json={"content": "What were we talking about?", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert res_c.status_code == 200
        data_c = res_c.json()
        assert data_c["task"] is None

        # TEST D — Persistent Cross-Session Memory Directive
        # Session 1: Store memory directive
        res_d1 = await client.post(
            "/api/v1/chat",
            json={"content": "Remember that VAL is my autonomous AI project", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert res_d1.status_code == 200
        data_d1 = res_d1.json()
        assert data_d1["message"]["metadata"]["intent"] == "MEMORY_STORE"

        # Session 2: Fresh conversation / simulated reload: "What am I building?"
        res_d2 = await client.post(
            "/api/v1/chat",
            json={"content": "What am I building?"},  # Fresh conversation (new conv_id)
            headers=auth_headers,
        )
        assert res_d2.status_code == 200
        data_d2 = res_d2.json()
        assert data_d2["message"]["metadata"]["intent"] == "MEMORY_QUERY"
        assert "VAL" in data_d2["message"]["content"] or "project" in data_d2["message"]["content"]

        # TEST F — Tool Selection and Execution ("What is 125 × 8?")
        res_f = await client.post(
            "/api/v1/chat",
            json={"content": "What is 125 × 8?"},
            headers=auth_headers,
        )
        assert res_f.status_code == 200
        data_f = res_f.json()
        assert data_f["message"]["metadata"]["intent"] == "COMMAND"
        assert "1,000" in data_f["message"]["content"] or "1000" in data_f["message"]["content"]

        # TEST H — Autonomous Learning Task ("Learn calculus and prepare to teach me")
        res_h = await client.post(
            "/api/v1/chat",
            json={"content": "Learn calculus and prepare to teach me"},
            headers=auth_headers,
        )
        assert res_h.status_code == 200
        data_h = res_h.json()
        assert data_h["message"]["metadata"]["intent"] == "AUTONOMOUS_TASK"
        assert data_h["task"] is not None
        assert "CALCULUS" in data_h["message"]["metadata"].get("agent_name", "")

        # Status Verification (Spec §18)
        res_status = await client.get("/api/v1/status", headers=auth_headers)
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["model_status"] in ["CONNECTED", "UNAVAILABLE"]
        assert status_data["memory_status"] == "CONNECTED"
        assert status_data["autonomy_status"] in ["RUNNING", "PAUSED"]


