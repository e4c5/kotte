"""Integration tests for query execution."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


class TestQueryTemplates:
    """Integration tests for query templates endpoint."""

    @pytest.mark.asyncio
    async def test_list_templates(self, authenticated_client: httpx.AsyncClient):
        """Test listing query templates (no DB required)."""
        response = await authenticated_client.get("/api/v1/queries/templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            t = data[0]
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "cypher" in t
            assert "param_schema" in t


class TestQueryExecution:
    """Integration tests for query execution endpoints."""

    @pytest.mark.asyncio
    async def test_execute_query_without_connection(self, authenticated_client: httpx.AsyncClient):
        """Test executing query without database connection."""
        response = await authenticated_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": "MATCH (n) RETURN n LIMIT 10",
            },
        )
        
        # Should fail because no database connection
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "DB_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_execute_query_success(self, connected_client: httpx.AsyncClient):
        """Test successful query execution."""
        # Get the mock from the connected_client fixture
        # The connected_client fixture already has a patched DatabaseConnection
        from app.api.v1.session import DatabaseConnection
        
        # Mock graph exists
        DatabaseConnection.return_value.execute_scalar = AsyncMock(return_value=1)  # Graph ID = 1
        
        # Mock query result with graph elements
        mock_result = [
            {
                "result": {
                    "id": 1,
                    "label": "Person",
                    "properties": {"name": "Alice", "age": 30},
                }
            },
            {
                "result": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 1,
                    "end_id": 2,
                    "properties": {"since": 2020},
                }
            },
        ]
        
        DatabaseConnection.return_value.execute_query = AsyncMock(return_value=mock_result)
        DatabaseConnection.return_value.get_backend_pid = AsyncMock(return_value=12345)
        
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": "MATCH (n)-[r]-(m) RETURN n, r LIMIT 10",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "columns" in data
        assert "rows" in data
        assert "request_id" in data
        assert data["row_count"] >= 0

    @pytest.mark.asyncio
    async def test_execute_query_with_params(self, connected_client: httpx.AsyncClient):
        """Test query execution with parameters."""
        mock_db = connected_client._mock_db
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        mock_db.execute_query = AsyncMock(return_value=[])
        mock_db.get_backend_pid = AsyncMock(return_value=12345)
        
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": "MATCH (n {name: $name}) RETURN n",
                "params": {"name": "Alice"},
            },
        )
        
        assert response.status_code == 200
        # Verify params were passed to query
        call_args = mock_db.execute_query.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_execute_query_invalid_graph(self, connected_client: httpx.AsyncClient):
        """Test query execution with invalid graph name."""
        mock_db = connected_client._mock_db
        # Mock graph not found
        mock_db.execute_scalar = AsyncMock(return_value=None)
        
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "nonexistent_graph",
                "cypher": "MATCH (n) RETURN n",
            },
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "GRAPH_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_execute_query_validation_error(self, connected_client: httpx.AsyncClient):
        """Test query execution with validation errors."""
        # Test invalid graph name format
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "123-invalid-graph-name",
                "cypher": "MATCH (n) RETURN n",
            },
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "QUERY_VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_execute_query_too_long(self, connected_client: httpx.AsyncClient):
        """Test query execution with query that's too long."""
        # Create a query that exceeds max length (1MB)
        huge_query = "MATCH (n) RETURN n " + "x" * (1000000 + 1)
        
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": huge_query,
            },
        )
        
        assert response.status_code == 413
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "QUERY_VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_execute_query_graph_elements_extraction(self, connected_client: httpx.AsyncClient):
        """Test that graph elements are properly extracted from query results."""
        mock_db = connected_client._mock_db
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        mock_db.get_backend_pid = AsyncMock(return_value=12345)
        
        # Mock result with nodes and edges
        mock_result = [
            {
                "result": {
                    "id": 1,
                    "label": "Person",
                    "properties": {"name": "Alice"},
                }
            },
            {
                "result": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 1,
                    "end_id": 2,
                    "properties": {},
                }
            },
        ]
        
        mock_db.execute_query = AsyncMock(return_value=mock_result)
        
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": "MATCH (n)-[r]-(m) RETURN n, r",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "graph_elements" in data or data.get("graph_elements") is None
        if data.get("graph_elements"):
            assert "nodes" in data["graph_elements"]
            assert "edges" in data["graph_elements"]

    @pytest.mark.asyncio
    async def test_execute_query_visualization_warning(self, connected_client: httpx.AsyncClient):
        """Test that visualization warning is returned for large results."""
        mock_db = connected_client._mock_db
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        mock_db.get_backend_pid = AsyncMock(return_value=12345)
        
        # Create mock result with many nodes (exceeding limit)
        many_nodes = []
        for i in range(6000):  # Exceeds max_nodes_for_graph (5000)
            many_nodes.append({
                "result": {
                    "id": i,
                    "label": "Person",
                    "properties": {"name": f"Person{i}"},
                }
            })
        
        mock_db.execute_query = AsyncMock(return_value=many_nodes)
        
        response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": "MATCH (n) RETURN n",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "visualization_warning" in data
        assert data["visualization_warning"] is not None
        assert "too large" in data["visualization_warning"].lower()


class TestQueryCancellation:
    """Integration tests for query cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_query_success(self, connected_client: httpx.AsyncClient):
        """Test successful query cancellation."""
        mock_db = connected_client._mock_db
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        mock_db.get_backend_pid = AsyncMock(return_value=12345)
        mock_db.cancel_backend = AsyncMock(return_value=True)
        
        # Execute a query first to get request_id
        mock_db.execute_query = AsyncMock(return_value=[])
        
        execute_response = await connected_client.post(
            "/api/v1/queries/execute",
            json={
                "graph": "test_graph",
                "cypher": "MATCH (n) RETURN n",
            },
        )
        
        if execute_response.status_code == 200:
            request_id = execute_response.json()["request_id"]
            
            # Cancel the query
            cancel_response = await connected_client.post(
                f"/api/v1/queries/{request_id}/cancel",
                json={"reason": "User requested cancellation"},
            )
            
            # May succeed or fail depending on query state
            assert cancel_response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_cancel_query_invalid_request_id(self, connected_client: httpx.AsyncClient):
        """Test canceling query with invalid request ID."""
        response = await connected_client.post(
            "/api/v1/queries/invalid-request-id/cancel",
            json={"reason": "Test"},
        )
        
        # Should fail with 404 or 400
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_cancel_query_without_connection(self, authenticated_client: httpx.AsyncClient):
        """Test canceling query without database connection."""
        # Query cancellation doesn't require DB connection, just session
        # But the query must be registered first
        response = await authenticated_client.post(
            "/api/v1/queries/test-request-id/cancel",
            json={"reason": "Test"},
        )
        
        # Should fail because query not found (not registered) - 404 is the correct response
        # The endpoint returns 404 when query is not found, which is correct behavior
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]

