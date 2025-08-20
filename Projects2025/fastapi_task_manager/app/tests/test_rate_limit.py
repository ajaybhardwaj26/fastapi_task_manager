from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)

@pytest.mark.asyncio
async def test_login_rate_limit():
    # Simulate exceeding rate limit (10/minute for /login)
    for _ in range(11):
        response = client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "wrong"})
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"

@pytest.mark.asyncio
async def test_task_create_rate_limit():
    # Login to get token
    login_response = client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "password123"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Simulate exceeding rate limit (50/minute for /tasks/)
    for _ in range(51):
        response = client.post("/api/v1/tasks/", json={"title": "Test Task"}, headers=headers)
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"