# tests/test_auth.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_user_login():
    response = client.post("/users/login", json={"email": "test@example.com", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_protected_route():
    login_response = client.post("/users/login", json={"email": "test@example.com", "password": "password123"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"