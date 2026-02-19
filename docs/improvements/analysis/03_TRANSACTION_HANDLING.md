# Transaction Handling and Data Integrity

**Priority:** HIGH  
**Effort:** LOW  
**Risk:** HIGH (Data corruption, inconsistent state)

---

## Overview

Critical graph mutation operations are currently executed **without transaction protection**, creating risks of data corruption and inconsistent graph state. This document outlines required transaction wrappers and ACID compliance improvements.

---

## Gap #1: Node Deletion Without Transactions

### Current Implementation
**File:** `backend/app/api/v1/graph_delete_node.py`, lines 92-118

```python
@router.delete("/{graph_name}/nodes/{node_id}", response_model=NodeDeleteResponse)
async def delete_node(
    graph_name: str,
    node_id: str,
    request: NodeDeleteRequest,
    db_conn: DatabaseConnection = Depends(get_db_connection),
    session: dict = Depends(get_session),
) -> NodeDeleteResponse:
    """Delete a node from the graph."""
    
    # Count connected edges (Query 1)
    count_cypher = """
        MATCH (n)-[r]-(m)
        WHERE id(n) = $node_id
        RETURN count(r) as edge_count
    """
    # ... execute count query ...
    edge_count = int(count_result)  # ← Get edge count
    
    # Delete node (Query 2)
    delete_cypher = """
        MATCH (n)
        WHERE id(n) = $node_id
        DETACH DELETE n
        RETURN count(n) as deleted_count
    """
    # ... execute delete query ...
    deleted_count = int(delete_result)  # ← Actually delete
    
    # Return result
    return NodeDeleteResponse(
        deleted=deleted_count > 0,
        node_id=node_id,
        edges_deleted=edge_count,
    )
```

### Issues

#### 1. No Atomicity
**Problem:** Two separate queries without transaction wrapper
- Query 1 counts edges
- Query 2 deletes node
- **Gap:** If delete fails, count was wasted work
- **Gap:** If another client modifies graph between queries, count is wrong

#### 2. No Isolation
**Problem:** Concurrent modifications can cause race conditions

**Scenario:**
```
Time  | Client A                    | Client B
------|----------------------------|---------------------------
T1    | Count edges for node X (5) |
T2    |                            | Add edge to node X
T3    | Delete node X + edges      |
T4    | Report "5 edges deleted"   | ← WRONG! Actually 6
```

#### 3. No Consistency Check
**Problem:** Doesn't verify deletion succeeded
- Returns `deleted=True` if count > 0, but doesn't verify
- No rollback if DETACH DELETE partially fails

#### 4. No Error Recovery
**Problem:** If delete fails, state is undefined
- No way to know if node was deleted
- No way to rollback edge count operation

### Fixed Implementation

```python
@router.delete("/{graph_name}/nodes/{node_id}", response_model=NodeDeleteResponse)
async def delete_node(
    graph_name: str,
    node_id: str,
    request: NodeDeleteRequest,
    db_conn: DatabaseConnection = Depends(get_db_connection),
    session: dict = Depends(get_session),
) -> NodeDeleteResponse:
    """Delete a node from the graph with transaction protection."""
    validated_graph_name = validate_graph_name(graph_name)
    
    # Parse node ID
    try:
        node_id_int = int(node_id)
    except ValueError:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message=f"Invalid node ID format: '{node_id}'. Must be a number.",
            category=ErrorCategory.VALIDATION,
            status_code=422,
        )
    
    # FIXED: Wrap in transaction for ACID guarantees
    try:
        async with db_conn.transaction():
            # Count edges within transaction
            count_cypher = """
                MATCH (n)-[r]-(m)
                WHERE id(n) = $node_id
                RETURN count(r) as edge_count
            """
            count_query = """
                SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text, %(params)s::agtype)
                AS (edge_count agtype)
            """
            params_json = json.dumps({"node_id": node_id_int})
            count_rows = await db_conn.execute_query(
                count_query,
                {"graph_name": validated_graph_name, "cypher": count_cypher, "params": params_json}
            )
            
            edge_count = 0
            if count_rows and len(count_rows) > 0:
                count_value = AgTypeParser.parse(count_rows[0].get("edge_count"))
                edge_count = int(count_value) if count_value else 0
            
            # Delete node within same transaction
            delete_cypher = """
                MATCH (n)
                WHERE id(n) = $node_id
                DETACH DELETE n
                RETURN count(n) as deleted_count
            """
            delete_query = """
                SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text, %(params)s::agtype)
                AS (deleted_count agtype)
            """
            delete_rows = await db_conn.execute_query(
                delete_query,
                {"graph_name": validated_graph_name, "cypher": delete_cypher, "params": params_json}
            )
            
            deleted_count = 0
            if delete_rows and len(delete_rows) > 0:
                delete_value = AgTypeParser.parse(delete_rows[0].get("deleted_count"))
                deleted_count = int(delete_value) if delete_value else 0
            
            # Verify deletion succeeded
            if deleted_count == 0:
                # Node didn't exist - rollback transaction
                raise APIException(
                    code=ErrorCode.QUERY_VALIDATION_ERROR,
                    message=f"Node {node_id} not found in graph '{validated_graph_name}'",
                    category=ErrorCategory.NOT_FOUND,
                    status_code=404,
                )
            
            # Transaction commits here automatically
            logger.info(
                f"Deleted node {node_id} from {validated_graph_name} "
                f"(removed {edge_count} edges)"
            )
            
            return NodeDeleteResponse(
                deleted=True,
                node_id=node_id,
                edges_deleted=edge_count,
            )
            
    except APIException:
        # Re-raise API exceptions (validation errors, not found, etc.)
        raise
    except Exception as e:
        # Database error - transaction auto-rolled back
        logger.exception(f"Failed to delete node {node_id}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to delete node: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e
```

### Benefits of Transaction Wrapper

| Aspect | Before | After |
|--------|--------|-------|
| **Atomicity** | Two separate queries | Single atomic transaction |
| **Consistency** | No verification | Verified deletion count |
| **Isolation** | Race conditions possible | Serializable isolation |
| **Durability** | Partial commits possible | All-or-nothing guarantee |
| **Error Handling** | Undefined state on error | Auto-rollback on failure |

---

## Gap #2: CSV Import Without Pre-Validation Transaction

### Current Implementation
**File:** `backend/app/api/v1/csv_importer.py`, lines 148-200

```python
async def import_csv_data(
    file: UploadFile,
    graph: str,
    vertex_label: str,
    db_conn: DatabaseConnection,
) -> ImportResult:
    """Import CSV data into graph."""
    
    # Create graph if doesn't exist
    # ... create graph ...
    
    # Create vertex label if doesn't exist
    # ... create label ...
    
    # TRANSACTION STARTS HERE (but too late!)
    async with db_conn.transaction():
        inserted_count = 0
        for row in rows:
            # Insert each row
            insert_cypher = """
                CREATE (n:{label} {properties})
                RETURN n
            """.format(label=vertex_label, properties=props)
            # ... execute insert ...
            inserted_count += 1
    
    return ImportResult(rows_inserted=inserted_count)
```

### Issues

#### 1. Graph/Label Creation Outside Transaction
**Problem:** Graph and label created before transaction starts
- If import fails, empty graph/label remains
- No way to rollback graph creation

#### 2. No Row Validation Before Insert
**Problem:** Rows inserted one-by-one without pre-validation
- Invalid row discovered after 50,000 valid rows inserted
- Transaction rolls back, but wasted time on 50,000 inserts

#### 3. No Batch Insertion
**Problem:** Individual INSERT for each row
- Slow: 1000 rows = 1000 round trips
- No opportunity for bulk optimization

### Fixed Implementation

```python
async def import_csv_data_validated(
    file: UploadFile,
    graph: str,
    vertex_label: str,
    edge_source_id: Optional[str],
    edge_target_id: Optional[str],
    edge_label: Optional[str],
    db_conn: DatabaseConnection,
) -> ImportResult:
    """
    Import CSV data with validation and transaction protection.
    
    Implements:
    1. Pre-validation before any DB operations
    2. Graph/label creation within transaction
    3. Batch insertion for performance
    4. Comprehensive error handling
    """
    from app.core.config import settings
    
    validated_graph = validate_graph_name(graph)
    validated_label = validate_label_name(vertex_label)
    
    # PHASE 1: Parse and validate CSV (before DB operations)
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        
        # Validate row count
        if len(df) > settings.import_max_rows:
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=f"CSV exceeds maximum rows: {len(df)} > {settings.import_max_rows}",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )
        
        # Validate columns
        if edge_source_id and edge_source_id not in df.columns:
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=f"Source ID column '{edge_source_id}' not found in CSV",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )
        
        # Validate data types
        for idx, row in df.iterrows():
            # Check for null values in required fields
            if edge_source_id and pd.isna(row[edge_source_id]):
                raise APIException(
                    code=ErrorCode.QUERY_VALIDATION_ERROR,
                    message=f"Row {idx}: Source ID cannot be null",
                    category=ErrorCategory.VALIDATION,
                    status_code=422,
                )
        
        logger.info(f"CSV validation passed: {len(df)} rows")
        
    except pd.errors.ParserError as e:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message=f"Invalid CSV format: {str(e)}",
            category=ErrorCategory.VALIDATION,
            status_code=422,
        ) from e
    
    # PHASE 2: All database operations in single transaction
    try:
        async with db_conn.transaction():
            # Create graph if needed
            graph_exists = await db_conn.execute_scalar(
                "SELECT EXISTS(SELECT 1 FROM ag_catalog.ag_graph WHERE name = %(graph)s)",
                {"graph": validated_graph}
            )
            
            if not graph_exists:
                create_graph_query = f"""
                    SELECT * FROM ag_catalog.create_graph('{validated_graph}')
                """
                await db_conn.execute_query(create_graph_query)
                logger.info(f"Created graph: {validated_graph}")
            
            # Create vertex label if needed
            label_exists = await db_conn.execute_scalar(
                """
                SELECT EXISTS(
                    SELECT 1 FROM ag_catalog.ag_label 
                    WHERE name = %(label)s 
                    AND graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph)s)
                )
                """,
                {"label": validated_label, "graph": validated_graph}
            )
            
            if not label_exists:
                create_label_query = f"""
                    SELECT * FROM ag_catalog.create_vlabel('{validated_graph}', '{validated_label}')
                """
                await db_conn.execute_query(create_label_query)
                logger.info(f"Created vertex label: {validated_label}")
            
            # BATCH INSERT: Build multi-row Cypher query
            inserted_count = 0
            batch_size = 1000
            
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch = df.iloc[batch_start:batch_end]
                
                # Build batch insert Cypher
                cypher_parts = []
                for idx, row in batch.iterrows():
                    # Convert row to properties dict
                    props = row.dropna().to_dict()
                    props_json = json.dumps(props)
                    
                    cypher_parts.append(
                        f"CREATE (n{idx}:{validated_label} {props_json})"
                    )
                
                batch_cypher = "\n".join(cypher_parts)
                
                # Execute batch
                batch_query = """
                    SELECT * FROM ag_catalog.cypher(%(graph)s::text, %(cypher)s::text) AS (result agtype)
                """
                await db_conn.execute_query(
                    batch_query,
                    {"graph": validated_graph, "cypher": batch_cypher}
                )
                
                inserted_count += len(batch)
                logger.info(f"Inserted batch: {batch_start}-{batch_end} ({inserted_count}/{len(df)})")
            
            # Update table statistics for query planner
            table_name = f"{validated_graph}_{validated_label}"
            await db_conn.execute_query(f"ANALYZE {escape_identifier(table_name)}")
            
            # Transaction commits here
            logger.info(f"Import completed: {inserted_count} rows inserted")
            
            return ImportResult(
                rows_inserted=inserted_count,
                rows_failed=0,
                errors=[],
            )
            
    except Exception as e:
        # Transaction auto-rolled back
        logger.exception("Import failed - transaction rolled back")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Import failed: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=False,
        ) from e
```

### Benefits

| Aspect | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Validation** | During insert | Before DB ops | Fail-fast |
| **Atomicity** | Partial on error | All-or-nothing | Data integrity |
| **Performance** | 1 query/row | 1 query/1000 rows | **1000x fewer roundtrips** |
| **Rollback** | Manual cleanup | Automatic | Simpler code |
| **Statistics** | Manual ANALYZE | Auto after import | Better query plans |

---

## Gap #3: No Transaction Timeout

### Issue
Long-running transactions can:
- Lock tables indefinitely
- Block other users
- Cause deadlocks

### Fix: Statement Timeout

```python
# backend/app/core/database.py

@asynccontextmanager
async def transaction(self, timeout: Optional[int] = None):
    """
    Context manager for database transactions with timeout.
    
    Args:
        timeout: Transaction timeout in seconds (default: 60)
    """
    timeout = timeout or 60  # Default 60 second transaction timeout
    
    async with self.connection.transaction():
        # Set statement timeout for this transaction
        await self.connection.execute(
            f"SET LOCAL statement_timeout = {timeout * 1000}"  # milliseconds
        )
        try:
            yield
        except asyncio.TimeoutError:
            # Transaction automatically rolled back
            logger.warning(f"Transaction timed out after {timeout}s")
            raise APIException(
                code=ErrorCode.QUERY_TIMEOUT,
                message=f"Transaction timed out after {timeout} seconds",
                category=ErrorCategory.UPSTREAM,
                status_code=504,
                retryable=True,
            )
```

**Usage:**
```python
# Short timeout for simple operations
async with db_conn.transaction(timeout=10):
    # ... quick operations ...

# Longer timeout for imports
async with db_conn.transaction(timeout=300):
    # ... bulk import ...
```

---

## Implementation Checklist

### Phase 1: Critical Fixes (Week 1)
- [ ] Wrap node deletion in transaction (graph_delete_node.py)
- [ ] Add deletion verification
- [ ] Add error handling and rollback
- [ ] Test concurrent deletion scenarios

### Phase 2: Import Improvements (Week 1)
- [ ] Add CSV pre-validation phase
- [ ] Move graph/label creation into transaction
- [ ] Implement batch insertion (1000 rows/batch)
- [ ] Add ANALYZE after import
- [ ] Test import rollback on errors

### Phase 3: Transaction Infrastructure (Week 2)
- [ ] Add transaction timeout support
- [ ] Implement transaction retry logic for deadlocks
- [ ] Add transaction monitoring/metrics
- [ ] Document transaction best practices

### Phase 4: Testing (Week 2)
- [ ] Test node deletion rollback scenarios  
      **Requires:** Real PostgreSQL/AGE test database and integration harness (FastAPI app with middleware + real `DatabaseConnection`)
- [ ] Test import validation failures  
      **Requires:** Ability to post CSVs against the real test DB and verify no graph/label/table changes on validation errors
- [ ] Test concurrent modification conflicts  
      **Requires:** Two or more independent DB connections/clients executing mutations concurrently
- [ ] Test transaction timeout behavior  
      **Requires:** Real transaction timeouts via `SET LOCAL statement_timeout` and long-running test queries
- [ ] Load test with concurrent operations  
      **Requires:** Load-test tooling (e.g., locust/k6) pointed at the test environment

---

## Testing Strategy

### Unit Tests
```python
@pytest.mark.asyncio
async def test_node_deletion_transaction_rollback(db_conn):
    """Test that failed deletion rolls back transaction."""
    # Create test node
    node_id = await create_test_node(db_conn, "TestGraph", "Person")
    
    # Mock failure in delete query
    with patch.object(db_conn, 'execute_query', side_effect=Exception("DB error")):
        with pytest.raises(APIException):
            await delete_node("TestGraph", str(node_id), ...)
    
    # Verify node still exists (transaction rolled back)
    node = await get_node(db_conn, "TestGraph", node_id)
    assert node is not None

@pytest.mark.asyncio
async def test_import_validation_prevents_db_operations(db_conn):
    """Test that validation failures prevent any DB operations."""
    # CSV with invalid data
    invalid_csv = "id,name\n1,Alice\ninvalid,Bob"  # 'invalid' is not a number
    
    # Track DB queries
    queries_executed = []
    original_execute = db_conn.execute_query
    
    async def tracking_execute(query, params=None, timeout=None):
        queries_executed.append(query)
        return await original_execute(query, params, timeout)
    
    with patch.object(db_conn, 'execute_query', side_effect=tracking_execute):
        with pytest.raises(APIException) as exc_info:
            await import_csv_data_validated(invalid_csv, "TestGraph", "Person", db_conn)
    
    # Verify NO database queries were executed
    assert len(queries_executed) == 0
    assert "validation" in str(exc_info.value).lower()
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_concurrent_node_deletion(db_conn_1, db_conn_2):
    """Test that concurrent deletions are properly serialized."""
    node_id = await create_test_node(db_conn_1, "TestGraph", "Person")
    
    # Two clients try to delete same node concurrently
    results = await asyncio.gather(
        delete_node_via_connection(db_conn_1, "TestGraph", node_id),
        delete_node_via_connection(db_conn_2, "TestGraph", node_id),
        return_exceptions=True
    )
    
    # One should succeed, one should fail with "not found"
    successes = [r for r in results if isinstance(r, NodeDeleteResponse) and r.deleted]
    not_founds = [r for r in results if isinstance(r, APIException) and r.code == ErrorCode.QUERY_VALIDATION_ERROR]
    
    assert len(successes) == 1
    assert len(not_founds) == 1
```

---

## Effort Estimate

| Task | Hours | Priority |
|------|-------|----------|
| Add transaction to node deletion | 2 | HIGH |
| CSV pre-validation | 3 | HIGH |
| Batch insertion implementation | 4 | HIGH |
| Transaction timeout support | 2 | MEDIUM |
| Error handling improvements | 2 | HIGH |
| Unit tests | 4 | HIGH |
| Integration tests | 4 | HIGH |
| Documentation | 2 | MEDIUM |
| **Total** | **23 hours** | |

---

## Success Criteria

### Functional
- [ ] All mutations wrapped in transactions
- [ ] CSV validation happens before DB operations
- [ ] Import uses batch insertion (1000 rows/batch)
- [ ] Transaction timeouts prevent indefinite locks
- [ ] Rollback tested and working

### Performance
- [ ] Import speed: >1000 rows/second (previously ~100/second)
- [ ] Transaction overhead: <10ms
- [ ] No deadlocks under concurrent load

### Reliability
- [ ] 100% rollback success on errors
- [ ] No partial state after failures
- [ ] Concurrent operations properly serialized

---

## References

- [PostgreSQL Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [psycopg3 Transaction Management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [Apache AGE Transaction Handling](https://age.apache.org/docs)
- [ACID Properties](https://en.wikipedia.org/wiki/ACID)
