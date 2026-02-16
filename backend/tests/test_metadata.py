"""Tests for metadata service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.metadata import MetadataService


class TestMetadataService:
    """Tests for metadata discovery service."""

    @pytest.mark.asyncio
    async def test_discover_properties_node_label(self, mock_db_connection):
        """Test discovering properties for a node label."""
        # Mock database query result
        mock_result = [
            {"properties": {"name": "Alice", "age": 30}},
            {"properties": {"name": "Bob", "age": 25, "city": "NYC"}},
        ]
        mock_db_connection.execute_query = AsyncMock(return_value=mock_result)
        
        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "Person", "v"
        )
        
        # Should return all unique property keys
        assert isinstance(properties, list)
        assert "name" in properties
        assert "age" in properties
        assert "city" in properties

    @pytest.mark.asyncio
    async def test_discover_properties_edge_label(self, mock_db_connection):
        """Test discovering properties for an edge label."""
        mock_result = [
            {"properties": {"since": 2020}},
            {"properties": {"since": 2021, "weight": 0.8}},
        ]
        mock_db_connection.execute_query = AsyncMock(return_value=mock_result)
        
        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "KNOWS", "e"
        )
        
        assert isinstance(properties, list)
        assert "since" in properties
        assert "weight" in properties

    @pytest.mark.asyncio
    async def test_discover_properties_empty_result(self, mock_db_connection):
        """Test discovering properties when no data exists."""
        mock_db_connection.execute_query = AsyncMock(return_value=[])
        
        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "EmptyLabel", "v"
        )
        
        assert isinstance(properties, list)
        assert len(properties) == 0

    @pytest.mark.asyncio
    async def test_discover_properties_no_properties(self, mock_db_connection):
        """Test discovering properties when nodes have no properties."""
        mock_result = [
            {"properties": {}},
            {"properties": None},
        ]
        mock_db_connection.execute_query = AsyncMock(return_value=mock_result)
        
        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "Person", "v"
        )
        
        assert isinstance(properties, list)
        # Should handle None/empty properties gracefully
        assert len(properties) == 0

