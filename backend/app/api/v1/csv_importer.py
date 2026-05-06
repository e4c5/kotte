"""CSV import endpoints."""

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File, Form

from app.core.auth import get_session
from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import validate_graph_name, validate_label_name, escape_string_literal
from app.services.metadata import MetadataService, invalidate_property_metadata_cache
from app.models.import_models import (
    CSVImportResponse,
    ImportJobStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job store (use Redis/DB in production)
_import_jobs: dict[str, ImportJobStatus] = {}


def _cleanup_import_jobs() -> None:
    """Remove stale jobs by TTL and evict oldest if over max size."""
    now = datetime.now(timezone.utc)
    ttl_secs = settings.import_job_ttl_seconds
    max_jobs = settings.max_import_jobs

    # TTL eviction: remove jobs older than JOB_TTL_SECONDS
    to_remove: list[str] = []
    for job_id, job in _import_jobs.items():
        ts_str = job.started_at or job.completed_at
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if (now - ts).total_seconds() > ttl_secs:
                to_remove.append(job_id)
        except (ValueError, TypeError):
            pass
    for job_id in to_remove:
        del _import_jobs[job_id]

    # Size eviction: remove oldest when over cap (dict preserves insertion order)
    while len(_import_jobs) >= max_jobs and _import_jobs:
        oldest_id = next(iter(_import_jobs))
        del _import_jobs[oldest_id]


def get_db_connection(session: Annotated[dict, Depends(get_session)]) -> DatabaseConnection:
    """Get database connection from session."""
    db_conn = session.get("db_connection")
    if not db_conn:
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message="Database connection not established",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        )
    return db_conn


@router.post("/csv")
async def import_csv(
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
    graph_name: str = Form(...),
    file: UploadFile = File(...),
    node_label: str = Form(None),
    edge_label: str = Form(None),
    drop_if_exists: bool = Form(False),
) -> CSVImportResponse:
    """
    Import CSV file to create graph data.

    This is a simplified synchronous implementation.
    For large files, this should be async with background jobs.
    """
    job_id = str(uuid.uuid4())

    # PHASE 1: CSV pre-validation before any database operations
    # Create job status
    job_status = ImportJobStatus(
        job_id=job_id,
        status="running",
        phase="reading_file",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _cleanup_import_jobs()
    _import_jobs[job_id] = job_status

    try:
        # Read CSV file
        content = await file.read()
        if len(content) > settings.import_max_file_size:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file exceeds maximum allowed size",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file is empty or has no header",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )
        # Strip BOM / whitespace from field names
        header = [f.strip().lstrip("﻿") for f in reader.fieldnames]
        # Case-insensitive lookup: lowercase → original header name
        header_lower_map = {h.lower(): h for h in header}
        if not header:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file has no header",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Read all rows now so we can enforce limits and re-iterate later
        try:
            all_rows: list[dict] = [
                {h: row.get(f, "").strip() for h, f in zip(header, (reader.fieldnames or []))}
                for row in reader
            ]
        except csv.Error as exc:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message=f"CSV parse error: {exc}",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            ) from exc

        row_count = len(all_rows)
        if row_count > settings.import_max_rows:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message=f"CSV file has too many rows ({row_count} > {settings.import_max_rows})",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Determine label type
        label = node_label or edge_label
        label_kind = "v" if node_label else "e"

        if not label:
            raise APIException(
                code=ErrorCode.IMPORT_VALIDATION_ERROR,
                message="Either node_label or edge_label must be provided",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Basic structural validation for edge CSV
        if label_kind == "e":
            required_edge_columns = {"source", "target"}
            missing = required_edge_columns - {h.lower() for h in header}
            if missing:
                raise APIException(
                    code=ErrorCode.IMPORT_INVALID_FILE,
                    message=f"Edge CSV is missing required columns: {', '.join(sorted(missing))}",
                    category=ErrorCategory.VALIDATION,
                    status_code=422,
                )

        # PHASE 2: All database operations in a single transaction
        validated_graph_name = validate_graph_name(graph_name)
        validated_label_name = validate_label_name(label)
        graph_lit = escape_string_literal(validated_graph_name)
        label_lit = escape_string_literal(validated_label_name)

        inserted = 0
        rejected = 0
        errors: list[str] = []

        async with db_conn.transaction(time_limit_seconds=300) as conn:
            # Ensure graph exists inside transaction
            graph_check = """
                SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
            """
            graph_id = await db_conn.execute_scalar(
                graph_check, {"graph_name": validated_graph_name}, conn=conn
            )

            if not graph_id:
                create_graph_query = f"""
                    SELECT * FROM ag_catalog.create_graph({graph_lit})
                """
                try:
                    await db_conn.execute_query(create_graph_query, conn=conn)
                    logger.info(f"Created graph: {validated_graph_name}")
                except Exception as e:
                    raise APIException(
                        code=ErrorCode.GRAPH_CONTEXT_INVALID,
                        message=f"Failed to create graph: {str(e)}",
                        category=ErrorCategory.UPSTREAM,
                        status_code=500,
                    ) from e

            # Create label if needed (inside same transaction)
            if drop_if_exists:
                drop_query = f"""
                    SELECT * FROM ag_catalog.drop_label({graph_lit}, {label_lit}, {label_kind == 'v'})
                """
                try:
                    await db_conn.execute_query(drop_query, conn=conn)
                except Exception:
                    # Label might not exist; that's fine when dropping conditionally
                    pass

            create_label_query = f"""
                SELECT * FROM ag_catalog.create_label({graph_lit}, {label_lit}, {label_kind == 'v'})
            """
            try:
                await db_conn.execute_query(create_label_query, conn=conn)
                job_status.created_labels.append(validated_label_name)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise

            # Batch insertion using parameterized UNWIND — no string interpolation of user data.
            import json

            batch_size = 1000
            for batch_start in range(0, len(all_rows), batch_size):
                batch_rows = all_rows[batch_start : batch_start + batch_size]
                node_batch: list[dict] = []
                edge_batch: list[dict] = []

                for line_num, properties in enumerate(batch_rows, start=batch_start + 2):
                    source_col = header_lower_map.get("source")
                    target_col = header_lower_map.get("target")
                    if label_kind == "v":
                        node_batch.append(properties)
                    else:
                        if source_col not in properties or target_col not in properties:
                            rejected += 1
                            errors.append(f"Row {line_num}: missing source or target")
                            continue
                        try:
                            source_id = int(properties[source_col])
                            target_id = int(properties[target_col])
                        except (ValueError, TypeError):
                            rejected += 1
                            errors.append(f"Row {line_num}: source and target must be integers")
                            continue
                        props = {
                            k: v for k, v in properties.items() if k not in {source_col, target_col}
                        }
                        edge_batch.append(
                            {
                                "source": source_id,
                                "target": target_id,
                                "props": props,
                            }
                        )

                if node_batch:
                    # UNWIND with JSON-encoded properties avoids per-row f-string injection.
                    rows_json = json.dumps(node_batch).replace("'", "''")
                    cypher = (
                        f"UNWIND {rows_json}::jsonb AS row "
                        f"CREATE (n:{validated_label_name}) "
                        f"SET n = row"
                    )
                    batch_query = """
                        SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text) AS (result agtype)
                    """
                    await db_conn.execute_query(
                        batch_query,
                        {"graph_name": validated_graph_name, "cypher": cypher},
                        conn=conn,
                    )
                    inserted += len(node_batch)

                if edge_batch:
                    # UNWIND with parameterized JSON — no user data interpolated via f-strings.
                    edges_json = json.dumps(
                        [{"s": e["source"], "t": e["target"], "p": e["props"]} for e in edge_batch]
                    ).replace("'", "''")
                    cypher = (
                        f"UNWIND {edges_json}::jsonb AS row "
                        f"MATCH (a), (b) "
                        f"WHERE id(a) = toInteger(row.s) AND id(b) = toInteger(row.t) "
                        f"CREATE (a)-[r:{validated_label_name}]->(b) "
                        f"SET r = row.p"
                    )
                    batch_query = """
                        SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text) AS (result agtype)
                    """
                    await db_conn.execute_query(
                        batch_query,
                        {"graph_name": validated_graph_name, "cypher": cypher},
                        conn=conn,
                    )
                    inserted += len(edge_batch)

        job_status.status = "completed"
        job_status.inserted_rows = inserted
        job_status.rejected_rows = rejected
        job_status.errors = errors[:100]  # Limit errors
        job_status.completed_at = datetime.now(timezone.utc).isoformat()
        job_status.progress = 1.0

        try:
            await invalidate_property_metadata_cache(validated_graph_name, validated_label_name)
        except Exception as e:
            logger.warning(
                "Post-import metadata cache invalidation failed for graph=%s label=%s: %s",
                validated_graph_name,
                validated_label_name,
                e,
                exc_info=True,
            )

        try:
            await MetadataService.analyze_table(db_conn, validated_graph_name, validated_label_name)
        except Exception as e:
            logger.warning(
                "Post-import ANALYZE failed for graph=%s label=%s: %s",
                validated_graph_name,
                validated_label_name,
                e,
                exc_info=True,
            )

        return CSVImportResponse(
            job_id=job_id,
            status="completed",
            message=f"Imported {inserted} rows, {rejected} rejected",
        )

    except APIException:
        job_status.status = "failed"
        job_status.completed_at = datetime.now(timezone.utc).isoformat()
        raise
    except Exception as e:
        logger.exception("CSV import failed")
        job_status.status = "failed"
        job_status.errors.append(str(e))
        job_status.completed_at = datetime.now(timezone.utc).isoformat()
        raise APIException(
            code=ErrorCode.IMPORT_FAILED,
            message=f"Import failed: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        ) from e


@router.get("/jobs/{job_id}")
async def get_import_job_status(
    job_id: str,
    session: Annotated[dict, Depends(get_session)],
) -> ImportJobStatus:
    """Get import job status."""
    _cleanup_import_jobs()
    job = _import_jobs.get(job_id)
    if not job:
        raise APIException(
            code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            message=f"Import job {job_id} not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )

    return job
