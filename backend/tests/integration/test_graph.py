"""Integration tests for graph endpoints."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


class TestGraphEndpoints:
    """Integration tests for graph metadata endpoints."""

    @pytest.mark.asyncio
    async def test_list_graphs_without_connection(self, authenticated_client: httpx.AsyncClient):
        """Test listing graphs without database connection."""
        response = await authenticated_client.get("/api/v1/graphs")
        
        # Should fail because no database connection
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "DB_UNAVAILABLE"

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_list_graphs_success(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test successful graph listing."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        
        # Mock graph list result
        mock_result = [
            {"name": "test_graph", "graphid": 1},
            {"name": "another_graph", "graphid": 2},
        ]
        mock_db.execute_query = AsyncMock(return_value=mock_result)
        
        response = await connected_client.get("/api/v1/graphs")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "name" in data[0]
            assert "id" in data[0]

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_get_graph_metadata_without_connection(self, mock_db_class, authenticated_client: httpx.AsyncClient):
        """Test getting graph metadata without database connection."""
        response = await authenticated_client.get("/api/v1/graphs/test_graph/metadata")
        
        assert response.status_code == 500

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_get_graph_metadata_success(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test getting graph metadata."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        
        # Mock graph exists
        mock_db.execute_scalar = AsyncMock(return_value=1)
        
        # Mock node labels
        mock_db.execute_query = AsyncMock(side_effect=[
            [{"label_name": "Person"}, {"label_name": "Company"}],  # Node labels
            [{"label_name": "KNOWS"}, {"label_name": "WORKS_FOR"}],  # Edge labels
        ])
        
        response = await connected_client.get("/api/v1/graphs/test_graph/metadata")
        
        assert response.status_code == 200
        data = response.json()
        assert "graph_name" in data
        assert "node_labels" in data
        assert "edge_labels" in data

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_get_graph_metadata_not_found(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test getting metadata for non-existent graph."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=None)  # Graph doesn't exist
        
        response = await connected_client.get("/api/v1/graphs/nonexistent_graph/metadata")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "GRAPH_NOT_FOUND"

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_get_graph_metadata_invalid_name(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test getting metadata with invalid graph name."""
        response = await connected_client.get("/api/v1/graphs/123-invalid-name/metadata")
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "QUERY_VALIDATION_ERROR"

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_get_meta_graph(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test getting meta-graph view."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        mock_db.execute_query = AsyncMock(return_value=[
            {"edge_label": "KNOWS"},
            {"edge_label": "WORKS_FOR"},
        ])
        
        response = await connected_client.get("/api/v1/graphs/test_graph/meta-graph")
        
        assert response.status_code == 200
        data = response.json()
        assert "graph_name" in data
        assert "relationships" in data


class TestNeighborhoodExpansion:
    """Integration tests for neighborhood expansion."""

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_without_connection(self, mock_db_class, authenticated_client: httpx.AsyncClient):
        """Test expanding node without database connection."""
        response = await authenticated_client.post(
            "/api/v1/graphs/test_graph/nodes/1/expand",
            json={"depth": 1, "limit": 100},
        )
        
        assert response.status_code == 500

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_success(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test successful neighborhood expansion."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        
        # Mock expansion result
        mock_result = [
            {
                "m": {
                    "id": 2,
                    "label": "Person",
                    "properties": {"name": "Bob"},
                },
                "rels": [
                    {
                        "id": 1,
                        "label": "KNOWS",
                        "start_id": 1,
                        "end_id": 2,
                        "properties": {},
                    }
                ],
            }
        ]
        
        mock_db.execute_query = AsyncMock(return_value=mock_result)
        
        response = await connected_client.post(
            "/api/v1/graphs/test_graph/nodes/1/expand",
            json={"depth": 1, "limit": 100},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "node_count" in data
        assert "edge_count" in data

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_invalid_graph(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test expanding node in non-existent graph."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=None)  # Graph doesn't exist
        
        response = await connected_client.post(
            "/api/v1/graphs/nonexistent_graph/nodes/1/expand",
            json={"depth": 1, "limit": 100},
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "GRAPH_NOT_FOUND"

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_invalid_node_id(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test expanding node with invalid node ID."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        
        response = await connected_client.post(
            "/api/v1/graphs/test_graph/nodes/invalid-id/expand",
            json={"depth": 1, "limit": 100},
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "QUERY_VALIDATION_ERROR"

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_invalid_depth(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test expanding node with invalid depth."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        
        # Test depth too high
        response = await connected_client.post(
            "/api/v1/graphs/test_graph/nodes/1/expand",
            json={"depth": 10, "limit": 100},  # Max depth is 5
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_invalid_limit(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test expanding node with invalid limit."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        
        # Test limit too high
        response = await connected_client.post(
            "/api/v1/graphs/test_graph/nodes/1/expand",
            json={"depth": 1, "limit": 2000},  # Max limit is 1000
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch('app.api.v1.graph.DatabaseConnection')
    async def test_expand_node_default_params(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test expanding node with default parameters."""
        mock_db = connected_client._mock_db if hasattr(connected_client, '_mock_db') else MagicMock()
        mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
        mock_db.execute_query = AsyncMock(return_value=[])
        
        response = await connected_client.post(
            "/api/v1/graphs/test_graph/nodes/1/expand",
            json={},  # Use defaults
        )
        
        # Should use default depth=1, limit=100
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

