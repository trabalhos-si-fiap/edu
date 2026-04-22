import os
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    """Base URL for the running stack. Override with E2E_BASE_URL env var."""
    return os.environ.get("E2E_BASE_URL", "http://localhost:8001")


@pytest.fixture
async def http(e2e_base_url: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(base_url=e2e_base_url, timeout=10.0) as client:
        yield client
