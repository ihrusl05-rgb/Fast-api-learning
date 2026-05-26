import sys
from pathlib import Path

import httpx
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.database import get_db
from main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
def override_db():
    def _override(session):
        async def _get_db():
            yield session

        app.dependency_overrides[get_db] = _get_db

    yield _override
    app.dependency_overrides.clear()
