import pytest
from httpx import RequestError
from app.worker import fetch_task_metadata

@pytest.mark.asyncio
async def test_fetch_task_metadata_retry(monkeypatch):
    async def mock_get(*args, **kwargs):
        raise RequestError("Network error")
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    with pytest.raises(RequestError):  # Should fail after 3 retries
        await fetch_task_metadata(1)