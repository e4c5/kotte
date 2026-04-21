#!/usr/bin/env python3
"""Reindex label tables across every AGE graph in the target database.

This is **not** an alembic migration — it's an operational task that
reads runtime catalog state (`ag_catalog.ag_graph` +
`ag_catalog.ag_label`) and creates `id` / `start_id` / `end_id` indices
on whatever labels exist right now. Because the catalog is dynamic (new
labels appear as users create them), a static alembic migration can't
express this; hence the separate script.

Relationship to the alembic migration chain (ROADMAP B7):
    * `make migrate-up`       — idempotent schema changes (AGE
                                extension, `kotte_users` stub, …).
    * `make reindex-labels`   — run this script. Safe to re-run whenever
                                new labels land; uses `IF NOT EXISTS`.

Usage:
    # Via environment variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
    python -m scripts.migrate_add_indices

    # Or via make (recommended):
    make reindex-labels

Creates id, start_id, end_id indices on all vertex and edge labels
in all AGE graphs. Safe to run multiple times (uses IF NOT EXISTS).
"""

import asyncio
import logging
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import DatabaseConnection
from app.services.metadata import MetadataService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_indices() -> None:
    """Create indices for all labels in all AGE graphs."""
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "5432"))
    database = os.environ.get("DB_NAME", "postgres")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "")

    db_conn = DatabaseConnection(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    try:
        await db_conn.connect()
    except Exception as e:
        logger.error("Failed to connect: %s", e)
        sys.exit(1)

    try:
        # Get all graphs
        graph_query = """
            SELECT name FROM ag_catalog.ag_graph ORDER BY name
        """
        graph_rows = await db_conn.execute_query(graph_query)
        graphs = [row["name"] for row in graph_rows]

        if not graphs:
            logger.info("No AGE graphs found")
            return

        logger.info("Found %d graph(s): %s", len(graphs), ", ".join(graphs))

        total_labels = 0
        for graph_name in graphs:
            # Get vertex labels
            v_query = """
                SELECT label.name as label_name
                FROM ag_catalog.ag_label label
                JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                WHERE graph.name = %(graph_name)s AND label.kind = 'v'
            """
            v_rows = await db_conn.execute_query(v_query, {"graph_name": graph_name})
            for row in v_rows:
                await MetadataService.create_label_indices(
                    db_conn, graph_name, row["label_name"], "v"
                )
                total_labels += 1

            # Get edge labels
            e_query = """
                SELECT label.name as label_name
                FROM ag_catalog.ag_label label
                JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            """
            e_rows = await db_conn.execute_query(e_query, {"graph_name": graph_name})
            for row in e_rows:
                await MetadataService.create_label_indices(
                    db_conn, graph_name, row["label_name"], "e"
                )
                total_labels += 1

        logger.info("Created/verified indices for %d label(s)", total_labels)

    finally:
        await db_conn.disconnect()


def main() -> None:
    asyncio.run(migrate_indices())


if __name__ == "__main__":
    main()
