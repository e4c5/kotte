"""CSV import endpoints."""

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.core.auth import get_session
from app.services.metadata import MetadataService, property_cache
from app.core.database import DatabaseConnection
from app.core.deps import get_db_connection
from app.core.errors import APIException, ErrorCode, ErrorCategory, translate_db_error
from app.core.validation import validate_graph_name, validate_label_name, escape_string_literal
from app.models.import_models import (
    CSVImportResponse,
    ImportJobStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job store (use Redis/DB in production)
_import_jobs: dict[str, ImportJobStatus] = {}


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

    # Validate graph name format (prevents SQL injection)
    validated_graph_name = validate_graph_name(graph_name)
    graph_lit = escape_string_literal(validated_graph_name)

    # Validate graph exists or create it (using parameterized query)
    graph_check = """
        SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
    """
    graph_id = await db_conn.execute_scalar(
        graph_check, {"graph_name": validated_graph_name}
    )

    if not graph_id:
        # Create graph if it doesn't exist
        # Note: create_graph() expects string literals, not identifiers.
        create_graph_query = f"""
            SELECT * FROM ag_catalog.create_graph({graph_lit})
        """
        try:
            await db_conn.execute_query(create_graph_query)
            logger.info(f"Created graph: {validated_graph_name}")
        except Exception as e:
            api_exc = translate_db_error(
                e, context={"graph": validated_graph_name, "operation": "create_graph"}
            )
            if api_exc:
                raise api_exc from e
            raise APIException(
                code=ErrorCode.GRAPH_CONTEXT_INVALID,
                message=f"Failed to create graph: {str(e)}",
                category=ErrorCategory.UPSTREAM,
                status_code=500,
                details={"graph": validated_graph_name},
            ) from e

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

    # Validate label name format (prevents SQL injection)
    validated_label = validate_label_name(label)
    label_lit = escape_string_literal(validated_label)

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
        # Parse CSV using the csv module to handle quoted fields and embedded commas
        text = content.decode("utf-8")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows or not rows[0]:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file is empty",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Parse header
        header = [col.strip() for col in rows[0]]
        if not header:
            raise APIException(
                code=ErrorCode.IMPORT_INVALID_FILE,
                message="CSV file has no header",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Create label if needed
        # Note: AGE label DDL doesn't support parameterization; validated + escaped
        # identifiers are used directly in the function calls below.
        if drop_if_exists:
            drop_query = f"""
                SELECT * FROM ag_catalog.drop_label({graph_lit}, {label_lit}, {'true' if label_kind == 'v' else 'false'})
            """
            try:
                await db_conn.execute_query(drop_query)
            except Exception:
                pass  # Label might not exist

        create_label_query = f"""
            SELECT * FROM ag_catalog.create_label({graph_lit}, {label_lit}, {'true' if label_kind == 'v' else 'false'})
        """
        try:
            await db_conn.execute_query(create_label_query)
            job_status.created_labels.append(validated_label)
        except Exception as e:
            if "already exists" in str(e).lower():
                pass  # Label exists, continue
            else:
                api_exc = translate_db_error(
                    e,
                    context={
                        "graph": validated_graph_name,
                        "label": validated_label,
                        "operation": "create_label",
                    },
                )
                if api_exc:
                    raise api_exc from e
                raise

        # Insert data in transaction
        inserted = 0
        rejected = 0
        errors = []

        async with db_conn.transaction():
            for line_num, row_values in enumerate(rows[1:], start=2):
                if not any(v.strip() for v in row_values):
                    continue

                values = [v.strip() for v in row_values]
                if len(values) != len(header):
                    rejected += 1
                    errors.append(f"Row {line_num}: column count mismatch")
                    continue

                # Build properties map
                properties = {
                    header[i]: values[i] for i in range(len(header))
                }

                # Insert node or edge
                # Use validated names (already validated for SQL injection)
                if label_kind == "v":
                    insert_query = f"""
                        SELECT * FROM ag_catalog.cypher('{validated_graph_name}'::text, $$
                            CREATE (n:{validated_label} $props)
                            RETURN n
                        $$::text, json_build_object('props', %(props)s::jsonb)::agtype) AS (result agtype)
                    """
                else:
                    # For edges, we need source and target
                    if "source" not in properties or "target" not in properties:
                        rejected += 1
                        errors.append(f"Row {line_num}: missing source or target")
                        continue

                    insert_query = f"""
                        SELECT * FROM ag_catalog.cypher('{validated_graph_name}'::text, $$
                            MATCH (a), (b)
                            WHERE id(a) = $source_id AND id(b) = $target_id
                            CREATE (a)-[r:{validated_label} $props]->(b)
                            RETURN r
                        $$::text, json_build_object(
                            'source_id', %(source_id)s,
                            'target_id', %(target_id)s,
                            'props', %(props)s::jsonb
                        )::agtype) AS (result agtype)
                    """

                try:
                    props_json = json.dumps(properties)
                    if label_kind == "v":
                        await db_conn.execute_query(
                            insert_query, {"props": props_json}
                        )
                    else:
                        await db_conn.execute_query(
                            insert_query,
                            {
                                "source_id": properties["source"],
                                "target_id": properties["target"],
                                "props": props_json,
                            },
                        )
                    inserted += 1
                except Exception as e:
                    rejected += 1
                    errors.append(f"Row {line_num}: {str(e)}")

        job_status.status = "completed"
        job_status.inserted_rows = inserted
        job_status.rejected_rows = rejected
        job_status.errors = errors[:100]  # Limit errors
        job_status.completed_at = datetime.now(timezone.utc).isoformat()
        job_status.progress = 1.0

        # Invalidate property cache so new properties are discovered
        property_cache.invalidate(validated_graph_name, validated_label)

        # Update table statistics for accurate count estimates
        await MetadataService.analyze_table(db_conn, validated_graph_name, validated_label)

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

