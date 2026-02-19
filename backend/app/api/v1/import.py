"""CSV import endpoints."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.core.auth import get_session
from app.services.metadata import MetadataService, property_cache
from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
from app.models.import import (
    CSVImportResponse,
    ImportJobStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job store (use Redis/DB in production)
_import_jobs: dict[str, ImportJobStatus] = {}


def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
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


@router.post("/csv", response_model=CSVImportResponse)
async def import_csv(
    graph_name: str = Form(...),
    node_label: str = Form(None),
    edge_label: str = Form(None),
    drop_if_exists: bool = Form(False),
    file: UploadFile = File(...),
    db_conn: DatabaseConnection = Depends(get_db_connection),
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

        lines = content.decode("utf-8").split("\n")
        if not lines or not lines[0].strip():
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file is empty",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Parse header
        header = [col.strip() for col in lines[0].split(",")]
        if not header:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file has no header",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Enforce maximum row limit
        row_count = max(0, len(lines) - 1)
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
            missing = required_edge_columns - set(header)
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
        safe_graph = escape_identifier(validated_graph_name)
        safe_label = escape_identifier(validated_label_name)

        inserted = 0
        rejected = 0
        errors: list[str] = []

        async with db_conn.transaction(timeout=300):
            # Ensure graph exists inside transaction
            graph_check = """
                SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
            """
            graph_id = await db_conn.execute_scalar(
                graph_check, {"graph_name": validated_graph_name}
            )

            if not graph_id:
                create_graph_query = f"""
                    SELECT * FROM ag_catalog.create_graph({safe_graph})
                """
                try:
                    await db_conn.execute_query(create_graph_query)
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
                    SELECT * FROM ag_catalog.drop_label({safe_graph}, {safe_label}, {label_kind == 'v'})
                """
                try:
                    await db_conn.execute_query(drop_query)
                except Exception:
                    # Label might not exist; that's fine when dropping conditionally
                    pass

            create_label_query = f"""
                SELECT * FROM ag_catalog.create_label({safe_graph}, {safe_label}, {label_kind == 'v'})
            """
            try:
                await db_conn.execute_query(create_label_query)
                job_status.created_labels.append(validated_label_name)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise

            # Batch insertion for better performance
            import json

            data_rows = [
                (line_num, line)
                for line_num, line in enumerate(lines[1:], start=2)
                if line.strip()
            ]

            batch_size = 1000
            for batch_start in range(0, len(data_rows), batch_size):
                batch = data_rows[batch_start : batch_start + batch_size]
                cypher_statements: list[str] = []

                for line_num, line in batch:
                    values = [v.strip() for v in line.split(",")]
                    if len(values) != len(header):
                        rejected += 1
                        errors.append(f"Row {line_num}: column count mismatch")
                        continue

                    properties = {
                        header[i]: values[i] for i in range(len(header))
                    }

                    if label_kind == "v":
                        props_json = json.dumps(properties).replace("'", "''")
                        cypher_statements.append(
                            f"CREATE (n:{validated_label_name} {props_json}::jsonb)"
                        )
                    else:
                        # For edges, ensure required IDs are present
                        if "source" not in properties or "target" not in properties:
                            rejected += 1
                            errors.append(f"Row {line_num}: missing source or target")
                            continue

                        props = {k: v for k, v in properties.items() if k not in {"source", "target"}}
                        props_json = json.dumps(props).replace("'", "''")
                        source_id = properties["source"]
                        target_id = properties["target"]
                        cypher_statements.append(
                            f"MATCH (a), (b) "
                            f"WHERE id(a) = {source_id} AND id(b) = {target_id} "
                            f"CREATE (a)-[r:{validated_label_name} {props_json}::jsonb]->(b)"
                        )

                if not cypher_statements:
                    continue

                batch_cypher = "\n".join(cypher_statements)
                batch_query = """
                    SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text) AS (result agtype)
                """
                await db_conn.execute_query(
                    batch_query,
                    {"graph_name": validated_graph_name, "cypher": batch_cypher},
                )

                inserted += len(cypher_statements)

        job_status.status = "completed"
        job_status.inserted_rows = inserted
        job_status.rejected_rows = rejected
        job_status.errors = errors[:100]  # Limit errors
        job_status.completed_at = datetime.now(timezone.utc).isoformat()
        job_status.progress = 1.0

        # Invalidate property cache so new properties are discovered
        property_cache.invalidate(validated_graph_name, validated_label_name)

        # Update table statistics for accurate count estimates
        await MetadataService.analyze_table(db_conn, validated_graph_name, validated_label_name)

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


@router.get("/jobs/{job_id}", response_model=ImportJobStatus)
async def get_import_job_status(
    job_id: str,
    session: dict = Depends(get_session),
) -> ImportJobStatus:
    """Get import job status."""
    job = _import_jobs.get(job_id)
    if not job:
        raise APIException(
            code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            message=f"Import job {job_id} not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )

    return job

