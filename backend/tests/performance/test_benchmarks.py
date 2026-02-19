"""Benchmark tests for performance validation.

Requires USE_REAL_TEST_DB=true and a test database with graphs.
Skipped when no test database is configured.
"""

import os
import pytest
import time


pytestmark = pytest.mark.performance


def _requires_real_db():
    return os.getenv("USE_REAL_TEST_DB", "false").lower() == "true"


@pytest.mark.skipif(not _requires_real_db(), reason="USE_REAL_TEST_DB not set")
class TestMetadataPerformance:
    """Benchmarks for metadata discovery."""

    @pytest.mark.asyncio
    async def test_metadata_discovery_speed(self):
        """Metadata discovery should complete in <500ms for graphs with <100k nodes."""
        pytest.skip("Requires async integration with real DB - implement when DB available")
        # Example structure:
        # start = time.perf_counter()
        # response = await client.get(f"/api/v1/graphs/{graph_name}/metadata")
        # elapsed = time.perf_counter() - start
        # assert elapsed < 0.5, f"Metadata took {elapsed:.2f}s (target <500ms)"


@pytest.mark.skipif(not _requires_real_db(), reason="USE_REAL_TEST_DB not set")
class TestQueryPerformance:
    """Benchmarks for query execution."""

    @pytest.mark.asyncio
    async def test_node_lookup_by_id_speed(self):
        """Node lookup by ID should be <10ms with indices."""
        pytest.skip("Requires async integration with real DB - implement when DB available")


@pytest.mark.skipif(not _requires_real_db(), reason="USE_REAL_TEST_DB not set")
class TestMetaGraphPerformance:
    """Benchmarks for meta-graph discovery."""

    @pytest.mark.asyncio
    async def test_meta_graph_discovery_speed(self):
        """Meta-graph discovery should complete in <1s for any graph size."""
        pytest.skip("Requires async integration with real DB - implement when DB available")
