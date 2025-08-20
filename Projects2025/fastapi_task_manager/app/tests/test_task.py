import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_task_filter_invalid_date():
    login_response = client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "password123"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/tasks/?created_after=invalid-date", headers=headers)
    assert response.status_code == 400
    assert "Invalid created_after date format" in response.json()["detail"]