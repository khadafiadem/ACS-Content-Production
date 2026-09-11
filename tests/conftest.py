import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_contents.db"
os.environ["TIKTOK_DRY_RUN"] = "true"
os.environ["GEMINI_API_KEY"] = "test"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient

import pytest

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c