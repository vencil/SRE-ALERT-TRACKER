"""Security tests — admin auth, SSRF validation, LLM key sanitization."""

import pytest


class TestAdminAuth:
    """Test admin endpoint authorization."""

    def test_admin_accessible_in_lab_mode(self, client):
        """Lab mode (AT_AUTH_MODE=none) allows admin access without restrictions."""
        res = client.get("/api/admin/retention")
        assert res.status_code == 200

    def test_admin_purge_accessible_in_lab_mode(self, client):
        """Lab mode allows purge access."""
        res = client.post("/api/admin/purge")
        assert res.status_code == 200


class TestSSRFValidation:
    """Test cluster URL validation against SSRF attacks."""

    def test_validate_cluster_url_blocks_metadata(self):
        """Block AWS/GCP metadata endpoint."""
        from config import validate_cluster_url
        with pytest.raises(ValueError, match="blocked host"):
            validate_cluster_url("http://169.254.169.254/latest/meta-data/", "prometheus_url")

    def test_validate_cluster_url_blocks_google_metadata(self):
        """Block GCP metadata endpoint."""
        from config import validate_cluster_url
        with pytest.raises(ValueError, match="blocked host"):
            validate_cluster_url("http://metadata.google.internal/computeMetadata/v1/", "prometheus_url")

    def test_validate_cluster_url_blocks_link_local(self):
        """Block link-local addresses."""
        from config import validate_cluster_url
        with pytest.raises(ValueError, match="link-local"):
            validate_cluster_url("http://169.254.1.1/api", "alertmanager_url")

    def test_validate_cluster_url_blocks_non_http(self):
        """Block non-http/https schemes."""
        from config import validate_cluster_url
        with pytest.raises(ValueError, match="only http/https"):
            validate_cluster_url("file:///etc/passwd", "prometheus_url")

    def test_validate_cluster_url_allows_valid(self):
        """Allow normal http/https URLs."""
        from config import validate_cluster_url
        assert validate_cluster_url("http://prometheus:9090", "prometheus_url") == "http://prometheus:9090"
        assert validate_cluster_url("https://prom.example.com", "url") == "https://prom.example.com"

    def test_validate_cluster_url_allows_empty(self):
        """Allow empty URL (optional field)."""
        from config import validate_cluster_url
        assert validate_cluster_url("", "url") == ""


class TestLLMKeySanitization:
    """Test that LLM API key is not exposed in error messages."""

    @pytest.mark.asyncio
    async def test_llm_http_error_sanitized(self):
        """HTTP errors should not expose auth headers."""
        import httpx
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized — Bearer sk-secret-key-12345",
            request=httpx.Request("POST", "http://api.example.com/v1/chat/completions"),
            response=mock_response,
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response

        with patch("config.settings.llm_provider", "openai"), \
             patch("config.settings.llm_api_key", "sk-secret-key-12345"), \
             patch("services.llm_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            from services.llm_service import generate_suggestion
            with pytest.raises(ValueError, match="HTTP 401") as exc_info:
                await generate_suggestion(
                    alert_name="TestAlert",
                    severity="warning",
                )
            # Ensure the API key is NOT in the error message
            assert "sk-secret-key" not in str(exc_info.value)
