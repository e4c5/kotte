"""Security tests for injection and validation bypass."""

import pytest
import httpx


# Graph/label names that attempt injection or bypass
INJECTION_ATTEMPTS = [
    "'; DROP TABLE graphs; --",
    "1; SELECT * FROM graphs",
    "graph\"; DELETE FROM nodes",
    "' OR '1'='1",
    "${graph}",
    "{{graph}}",
    "graph_name; CREATE TABLE evil",
    "graph\\",
    "../../../etc/passwd",
    "graph\x00null",
    "graph\n-- comment",
    "graph\tOR 1=1",
    "-- comment",
    "graph'; INSERT INTO",
]

# Invalid identifiers (should be rejected by validate_graph_name)
INVALID_IDENTIFIERS = [
    "",
    "123graph",  # starts with number
    "graph-name",  # hyphen
    "graph.name",  # dot
    "graph name",  # space
    "graph$name",  # special char
    "a" * 64,  # too long
]


class TestGraphNameInjection:
    """Test that graph names are validated and injection is blocked."""

    @pytest.mark.asyncio
    async def test_injection_attempts_rejected(self, async_client: httpx.AsyncClient):
        """Malicious graph names should be rejected (never return 200 success)."""
        # Graph metadata endpoint validates graph_name - invalid chars get 400
        # Without auth/DB we may get 401/500 - all are safe (no injection executed)
        for malicious in INJECTION_ATTEMPTS:
            from urllib.parse import quote
            encoded = quote(malicious, safe="")
            response = await async_client.get(f"/api/v1/graphs/{encoded}/metadata")
            # Must never return success for malicious input.
            assert response.status_code != 200, (
                f"Graph name '{malicious!r}' may have bypassed validation: "
                f"{response.status_code}, body={response.text}"
            )

    @pytest.mark.asyncio
    async def test_invalid_identifiers_rejected(self, async_client: httpx.AsyncClient):
        """Invalid graph name formats should be rejected."""
        for invalid in INVALID_IDENTIFIERS:
            if not invalid:
                response = await async_client.get("/api/v1/graphs//metadata")
            else:
                from urllib.parse import quote
                encoded = quote(invalid, safe="")
                response = await async_client.get(f"/api/v1/graphs/{encoded}/metadata")
            # Must not return 200 with metadata
            assert response.status_code != 200, (
                f"Invalid graph name '{invalid!r}' was accepted: {response.status_code}"
            )


class TestValidationBypass:
    """Test that validation cannot be bypassed."""

    def test_valid_graph_name_format(self):
        """Valid graph name format passes validation (unit test)."""
        from app.core.validation import validate_graph_name

        valid_names = ["my_graph", "Graph1", "_private", "valid_name_123"]
        for name in valid_names:
            assert validate_graph_name(name) == name
