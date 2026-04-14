"""Tests for the /chat/stream SSE endpoint."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from friday_ai.server import create_app


class TestStreamEndpoint:
    @pytest.mark.asyncio
    async def test_stream_endpoint_exists(self):
        """The /chat/stream endpoint should respond."""
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat/stream",
                json={"message": "Hi"},
            )
            # Should not return 404/405 — endpoint exists
            assert response.status_code != 404
            assert response.status_code != 405
