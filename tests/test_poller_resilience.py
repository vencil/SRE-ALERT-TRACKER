"""Tests for Poller HTTP resilience — timeout, 500, malformed JSON."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from models.cluster import Cluster
from services.alert_poller import pull_from_alertmanager, pull_from_prometheus


def _make_cluster() -> Cluster:
    """Create a mock Cluster object for testing."""
    cluster = MagicMock(spec=Cluster)
    cluster.name = "test-cluster"
    cluster.alertmanager_url = "http://am:9093"
    cluster.prometheus_url = "http://prom:9090"
    cluster.instance_label = "instance"
    return cluster


class TestAlertmanagerResilience:
    """Alertmanager pull should return [] on network errors, not crash."""

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.ReadTimeout("Connection timed out")

        result = await pull_from_alertmanager(cluster, client)
        assert result == []

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await pull_from_alertmanager(cluster, client)
        assert result == []

    @pytest.mark.asyncio
    async def test_http_500_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        client.get.return_value = mock_resp

        result = await pull_from_alertmanager(cluster, client)
        assert result == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = ValueError("Expecting value")
        client.get.return_value = mock_resp

        result = await pull_from_alertmanager(cluster, client)
        assert result == []


class TestPrometheusResilience:
    """Prometheus pull should return [] on network errors, not crash."""

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.ReadTimeout("Connection timed out")

        result = await pull_from_prometheus(cluster, client, lookback_hours=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_http_500_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        client.get.return_value = mock_resp

        result = await pull_from_prometheus(cluster, client, lookback_hours=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = ValueError("Expecting value")
        client.get.return_value = mock_resp

        result = await pull_from_prometheus(cluster, client, lookback_hours=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_prometheus_error_status_returns_empty(self):
        """Prometheus returns 200 but status='error' in JSON body."""
        cluster = _make_cluster()
        client = AsyncMock(spec=httpx.AsyncClient)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "status": "error",
            "errorType": "execution",
            "error": "query timed out",
        }
        client.get.return_value = mock_resp

        result = await pull_from_prometheus(cluster, client, lookback_hours=2)
        assert result == []
