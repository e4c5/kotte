"""Tests for metadata service."""

import pytest
from unittest.mock import AsyncMock

from app.services.metadata import MetadataService, property_cache


class TestMetadataService:
    """Tests for metadata discovery service."""

    @pytest.mark.asyncio
    async def test_discover_properties_node_label(self, mock_db_connection):
        """Test discovering properties for a node label (jsonb_object_keys format)."""
        property_cache.invalidate("test_graph", "Person")
        # Mock jsonb_object_keys query result: one row per distinct property key
        mock_result = [
            {"prop_key": "age"},
            {"prop_key": "city"},
            {"prop_key": "name"},
        ]
        mock_db_connection.execute_query = AsyncMock(return_value=mock_result)

        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "Person", "v"
        )

        assert isinstance(properties, list)
        assert "name" in properties
        assert "age" in properties
        assert "city" in properties

    @pytest.mark.asyncio
    async def test_discover_properties_edge_label(self, mock_db_connection):
        """Test discovering properties for an edge label (jsonb_object_keys format)."""
        property_cache.invalidate("test_graph", "KNOWS")
        mock_result = [
            {"prop_key": "since"},
            {"prop_key": "weight"},
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
        property_cache.invalidate("test_graph", "EmptyLabel")
        mock_db_connection.execute_query = AsyncMock(return_value=[])
        
        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "EmptyLabel", "v"
        )
        
        assert isinstance(properties, list)
        assert len(properties) == 0

    @pytest.mark.asyncio
    async def test_discover_properties_no_properties(self, mock_db_connection):
        """Test discovering properties when nodes have no properties."""
        property_cache.invalidate("test_graph", "NoPropsLabel")  # avoid cache from other tests
        # jsonb_object_keys returns no rows for empty/null properties
        mock_db_connection.execute_query = AsyncMock(return_value=[])

        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "NoPropsLabel", "v"
        )

        assert isinstance(properties, list)
        assert len(properties) == 0

    @pytest.mark.asyncio
    async def test_get_label_count_estimates(self, mock_db_connection):
        """Test fetching label count estimates in one query."""
        mock_db_connection.execute_query = AsyncMock(
            return_value=[
                {"label_name": "Person", "estimate": 123},
                {"label_name": "Company", "estimate": 45},
            ]
        )

        estimates = await MetadataService.get_label_count_estimates(
            mock_db_connection, "test_graph", "v"
        )

        assert estimates["Person"] == 123
        assert estimates["Company"] == 45

    @pytest.mark.asyncio
    async def test_get_numeric_property_statistics_for_label(self, mock_db_connection):
        """Test fetching numeric property stats for an edge/vertex label."""
        mock_db_connection.execute_query = AsyncMock(
            return_value=[
                {"property": "weight", "min": 0.1, "max": 0.9},
                {"property": "cost", "min": 1, "max": 10},
            ]
        )

        stats = await MetadataService.get_numeric_property_statistics_for_label(
            mock_db_connection, "test_graph", "REL"
        )

        assert stats["weight"]["min"] == 0.1
        assert stats["weight"]["max"] == 0.9
        assert stats["cost"]["min"] == 1.0
        assert stats["cost"]["max"] == 10.0

