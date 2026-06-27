from uuid import uuid4

from fastapi.testclient import TestClient

from core.app import app


def credentials(prefix: str):
    return {"username": f"{prefix}_{uuid4().hex[:10]}", "password": "StrongPass123!"}


def test_auth_and_conversation_isolation():
    with TestClient(app) as client:
        assert client.post("/api/auth/register", json=credentials("owner")).status_code == 201
        conversation = client.post("/api/conversations", json={"title": "private"}).json()
        assert client.get(f"/api/conversations/{conversation['id']}/messages").status_code == 200
        assert client.post("/api/auth/logout").status_code == 204
        assert client.post("/api/auth/register", json=credentials("other")).status_code == 201
        assert client.get(f"/api/conversations/{conversation['id']}/messages").status_code == 404


def test_unconfigured_model_rejects_stream():
    with TestClient(app) as client:
        assert client.post("/api/auth/register", json=credentials("guard")).status_code == 201
        conversation = client.post("/api/conversations", json={"title": "guard test"}).json()
        response = client.post(
            f"/api/conversations/{conversation['id']}/messages/stream",
            json={"content": "北辰项目内部底价是七折"},
        )
        assert response.status_code == 409
        assert "请先在设置中配置模型" in response.json()["detail"]
