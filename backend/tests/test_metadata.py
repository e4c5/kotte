"""Tests for metadata service."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.metadata import (
    MetadataService,
    invalidate_property_metadata_cache,
)
from app.services.cache import metadata_cache


class TestMetadataService:
    """Tests for metadata discovery service."""

    @pytest.mark.asyncio
    async def test_discover_properties_node_label(self, mock_db_connection):
        """Test discovering properties for a node label (Cypher keys() format)."""
        await metadata_cache.clear()
        # execute_cypher returns AS (k agtype); k is list of keys from keys(n)
        mock_result = [
            {"k": '["age", "city", "name"]'}, # Parser expects AgType string in some mocks, or list
        ]
        mock_db_connection.execute_cypher = AsyncMock(return_value=mock_result)

        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "Person", "v"
        )

        assert isinstance(properties, list)
        assert "name" in properties
        assert "age" in properties
        assert "city" in properties

    @pytest.mark.asyncio
    async def test_discover_properties_edge_label(self, mock_db_connection):
        """Test discovering properties for an edge label (Cypher keys() format)."""
        await metadata_cache.clear()
        mock_result = [
            {"k": '["since", "weight"]'},
        ]
        mock_db_connection.execute_cypher = AsyncMock(return_value=mock_result)

        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "KNOWS", "e"
        )

        assert isinstance(properties, list)
        assert "since" in properties
        assert "weight" in properties

    @pytest.mark.asyncio
    async def test_discover_properties_empty_result(self, mock_db_connection):
        """Test discovering properties when no data exists."""
        await metadata_cache.clear()
        mock_db_connection.execute_cypher = AsyncMock(return_value=[])

        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "EmptyLabel", "v"
        )

        assert isinstance(properties, list)
        assert len(properties) == 0

    @pytest.mark.asyncio
    async def test_discover_properties_no_properties(self, mock_db_connection):
        """Test discovering properties when nodes have no properties."""
        await metadata_cache.clear()
        mock_db_connection.execute_cypher = AsyncMock(return_value=[])

        properties = await MetadataService.discover_properties(
            mock_db_connection, "test_graph", "NoPropsLabel", "v"
        )

        assert isinstance(properties, list)
        assert len(properties) == 0

    @pytest.mark.asyncio
    async def test_get_label_count_estimates(self, mock_db_connection):
        """Test fetching label count estimates in one query."""
        await metadata_cache.clear()
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
        """Aggregates per-property min/max; skips non-numeric or empty stats."""
        with patch.object(
            MetadataService,
            "get_property_statistics",
            new=AsyncMock(
                side_effect=[
                    {"min": 1.0, "max": 3.0},
                    {"min": None, "max": None},
                ]
            ),
        ):
            stats = await MetadataService.get_numeric_property_statistics_for_label(
                mock_db_connection,
                "test_graph",
                "REL",
                properties=["w", "note"],
            )
        assert stats == {"w": {"min": 1.0, "max": 3.0}}

    @pytest.mark.asyncio
    async def test_get_numeric_property_statistics_for_label_empty_props(self, mock_db_connection):
        """No properties yields empty dict."""
        stats = await MetadataService.get_numeric_property_statistics_for_label(
            mock_db_connection, "test_graph", "REL", properties=[]
        )
        assert stats == {}


class TestInvalidatePropertyMetadataCache:
    """Lock-safe invalidation uses metadata_cache APIs."""

    @pytest.mark.asyncio
    async def test_clears_props_for_both_kinds_when_label_given(self):
        await metadata_cache.clear()
        await metadata_cache.set("props:g:L:v", ["a"], ttl_seconds=3600)
        await metadata_cache.set("props:g:L:e", ["b"], ttl_seconds=3600)
        await metadata_cache.set("props:g:Other:v", ["x"], ttl_seconds=3600)
        await invalidate_property_metadata_cache("g", "L")
        assert await metadata_cache.get("props:g:L:v") is None
        assert await metadata_cache.get("props:g:L:e") is None
        assert await metadata_cache.get("props:g:Other:v") is not None

    @pytest.mark.asyncio
    async def test_clears_props_counts_stats_prefixes_when_graph_only(self):
        await metadata_cache.clear()
        await metadata_cache.set("props:g:Person:v", [], ttl_seconds=3600)
        await metadata_cache.set("counts:g:v", {}, ttl_seconds=600)
        await metadata_cache.set("stats:g:L:v:age", {}, ttl_seconds=3600)
        await metadata_cache.set("props:other:Person:v", [], ttl_seconds=3600)
        await invalidate_property_metadata_cache("g")
        assert await metadata_cache.get("props:g:Person:v") is None
        assert await metadata_cache.get("counts:g:v") is None
        assert await metadata_cache.get("stats:g:L:v:age") is None
        assert await metadata_cache.get("props:other:Person:v") is not None
