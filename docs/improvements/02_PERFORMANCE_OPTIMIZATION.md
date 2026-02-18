# Performance Optimization

**Priority:** HIGH  
**Effort:** MEDIUM  
**Impact:** Significant performance improvement on large graphs

---

## Overview

The current implementation lacks database indexing and uses inefficient query patterns that cause performance degradation on graphs with >10,000 nodes. This document outlines critical performance optimizations needed for production deployment.

---

## Gap #1: Missing Database Indices

### Current State
**NO INDICES EXIST** on any graph tables. All queries perform full table scans.

### Impact
- **Metadata discovery:** 10-100x slower on large graphs
- **Node lookups by ID:** O(n) instead of O(log n)
- **Property filtering:** Full scans for every WHERE clause
- **Label counts:** Inefficient counting without statistics

### PostgreSQL EXPLAIN Analysis
```sql
-- Current query (no index)
EXPLAIN ANALYZE
SELECT properties 
FROM my_graph.Person 
WHERE properties->>'age' > '30'
LIMIT 100;

Result:
Seq Scan on person (cost=0.00..1849.00 rows=33 width=32) (actual time=245.123..486.456 rows=100 loops=1)
  Filter: ((properties->>'age')::int > 30)
  Rows Removed by Filter: 49900
Planning Time: 0.123 ms
Execution Time: 486.789 ms
```

### Recommended Indices

#### 1. Primary ID Index (Critical)
**Purpose:** Fast node/edge lookups by ID (used in expand, delete, etc.)

```sql
-- For each vertex label
CREATE INDEX idx_{graph}_{label}_id ON {graph}.{label}(id);

-- For each edge label  
CREATE INDEX idx_{graph}_{label}_id ON {graph}.{label}(id);
CREATE INDEX idx_{graph}_{label}_start ON {graph}.{label}(start_id);
CREATE INDEX idx_{graph}_{label}_end ON {graph}.{label}(end_id);
```

**Implementation:**
```python
# backend/app/services/metadata.py

async def create_label_indices(
    db_conn: DatabaseConnection,
    graph_name: str,
    label_name: str,
    label_kind: str,  # 'v' or 'e'
) -> None:
    """
    Create performance indices for a graph label.
    
    Creates:
    - ID index for fast lookups
    - Start/End indices for edges (relationship traversal)
    """
    from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
    
    validated_graph = validate_graph_name(graph_name)
    validated_label = validate_label_name(label_name)
    safe_graph = escape_identifier(validated_graph)
    safe_label = escape_identifier(validated_label)
    table_name = f"{safe_graph}.{safe_label}"
    
    try:
        # ID index (all labels)
        id_index_name = f"idx_{validated_graph}_{validated_label}_id"
        await db_conn.execute_query(f"""
            CREATE INDEX IF NOT EXISTS {escape_identifier(id_index_name)}
            ON {table_name}(id)
        """)
        logger.info(f"Created ID index for {table_name}")
        
        # Edge-specific indices
        if label_kind == 'e':
            # Start node index
            start_index_name = f"idx_{validated_graph}_{validated_label}_start"
            await db_conn.execute_query(f"""
                CREATE INDEX IF NOT EXISTS {escape_identifier(start_index_name)}
                ON {table_name}(start_id)
            """)
            
            # End node index
            end_index_name = f"idx_{validated_graph}_{validated_label}_end"
            await db_conn.execute_query(f"""
                CREATE INDEX IF NOT EXISTS {escape_identifier(end_index_name)}
                ON {table_name}(end_id)
            """)
            logger.info(f"Created edge indices for {table_name}")
            
    except Exception as e:
        logger.warning(f"Failed to create indices for {table_name}: {e}")
        # Don't fail - indices are optimization, not requirement
```

#### 2. Property Indices (On-Demand)
**Purpose:** Fast filtering on commonly queried properties

```python
async def create_property_index(
    db_conn: DatabaseConnection,
    graph_name: str,
    label_name: str,
    property_name: str,
) -> None:
    """
    Create GIN index on a specific property for fast filtering.
    
    Uses PostgreSQL's GIN (Generalized Inverted Index) for JSONB properties.
    """
    from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
    
    validated_graph = validate_graph_name(graph_name)
    validated_label = validate_label_name(label_name)
    safe_graph = escape_identifier(validated_graph)
    safe_label = escape_identifier(validated_label)
    table_name = f"{safe_graph}.{safe_label}"
    
    # GIN index for property existence and filtering
    index_name = f"idx_{validated_graph}_{validated_label}_prop_{property_name}"
    
    await db_conn.execute_query(f"""
        CREATE INDEX IF NOT EXISTS {escape_identifier(index_name)}
        ON {table_name} USING GIN (properties)
    """)
    logger.info(f"Created property index for {property_name} on {table_name}")
```

#### 3. Auto-Index Creation
**Trigger:** When a graph is first accessed or when metadata is retrieved

```python
# backend/app/api/v1/graph.py

@router.get("/{graph_name}/metadata", response_model=GraphMetadata)
async def get_graph_metadata(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
    create_indices: bool = True,  # Query parameter
) -> GraphMetadata:
    """Get metadata for a specific graph."""
    validated_graph_name = validate_graph_name(graph_name)
    
    # ... existing graph validation ...
    
    # Get node labels
    node_labels = []
    for row in node_label_rows:
        label_name = row["label_name"]
        validated_label_name = validate_label_name(label_name)
        
        # Create indices automatically (async, don't wait)
        if create_indices:
            asyncio.create_task(
                MetadataService.create_label_indices(
                    db_conn, validated_graph_name, validated_label_name, 'v'
                )
            )
        
        # ... rest of metadata discovery ...
```

### Performance Improvement Estimate
| Query Type | Before | After | Improvement |
|------------|--------|-------|-------------|
| Node lookup by ID | 250ms | 2ms | **125x faster** |
| Edge traversal | 500ms | 5ms | **100x faster** |
| Property filter | 1000ms | 50ms | **20x faster** |
| Metadata discovery | 5000ms | 100ms | **50x faster** |

---

## Gap #2: Inefficient Meta-Graph Discovery

### Current Implementation
**File:** `backend/app/api/v1/graph.py`, lines 233-313

**Problem:** N+1 query pattern
1. Query all edge labels (1 query)
2. For each edge label, sample 100 edges (N queries)
3. For each sampled edge, query node labels (2N queries)

**Total:** 1 + N + 2N = **3N + 1 queries** for N edge labels

```python
# Current inefficient code
edge_rows = await db_conn.execute_query(edge_query, {"graph_name": validated_graph_name})

relationships = []
for edge_row in edge_rows:  # ← Loop N times
    edge_label = edge_row["edge_label"]
    
    # Sample query (1 query per edge label)
    sample_query = f"""
        SELECT start_id, end_id
        FROM {validated_graph_name}.{validated_edge_label}
        LIMIT 100
    """
    samples = await db_conn.execute_query(sample_query)  # ← N queries
    
    # For each sample, query node labels (not shown, but would be 2N more queries)
```

### Optimized Implementation
**Single aggregation query** using Cypher

```python
@router.get("/{graph_name}/meta-graph", response_model=MetaGraphResponse)
async def get_meta_graph(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    validated_graph_name = validate_graph_name(graph_name)
    
    # Verify graph exists
    graph_check = """
        SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
    """
    graph_id = await db_conn.execute_scalar(graph_check, {"graph_name": validated_graph_name})
    if not graph_id:
        raise APIException(
            code=ErrorCode.GRAPH_NOT_FOUND,
            message=f"Graph '{validated_graph_name}' not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )
    
    # OPTIMIZED: Single Cypher query to get meta-graph
    meta_cypher = """
        MATCH (src)-[rel]->(dst)
        WITH labels(src)[0] as src_label, 
             type(rel) as rel_type,
             labels(dst)[0] as dst_label
        RETURN src_label, rel_type, dst_label, COUNT(*) as edge_count
        ORDER BY edge_count DESC
        LIMIT 1000
    """
    
    # Execute via AGE cypher function
    import json
    sql_query = """
        SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text) 
        AS (src_label agtype, rel_type agtype, dst_label agtype, edge_count agtype)
    """
    sql_params = {"graph_name": validated_graph_name, "cypher": meta_cypher}
    
    try:
        raw_rows = await db_conn.execute_query(sql_query, sql_params)
        
        relationships = []
        for row in raw_rows:
            # Parse agtype results
            src_label = AgTypeParser.parse(row["src_label"])
            rel_type = AgTypeParser.parse(row["rel_type"])
            dst_label = AgTypeParser.parse(row["dst_label"])
            count = AgTypeParser.parse(row["edge_count"])
            
            relationships.append(
                MetaGraphEdge(
                    source_label=str(src_label),
                    target_label=str(dst_label),
                    edge_label=str(rel_type),
                    count=int(count),
                )
            )
        
        return MetaGraphResponse(
            graph_name=validated_graph_name,
            relationships=relationships,
        )
        
    except Exception as e:
        logger.exception(f"Error getting meta-graph for {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get meta-graph: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e
```

### Performance Comparison
| Metric | Current (N+1) | Optimized (Single Query) | Improvement |
|--------|---------------|--------------------------|-------------|
| Queries executed | 3N + 1 | 1 | **3N+1 → 1** |
| Time (10 edge labels) | 3.5s | 0.2s | **17.5x faster** |
| Time (100 edge labels) | 35s | 0.3s | **116x faster** |
| Network roundtrips | 301 | 1 | **301x fewer** |

---

## Gap #3: Property Discovery Inefficiency

### Current Implementation
**File:** `backend/app/services/metadata.py`, lines 20-76

**Problem:** Samples first N records to discover properties
- Misses rare properties (appears only in record N+1)
- No caching of discovered properties
- Repeated sampling on every metadata request

```python
# Current code
async def discover_properties(db_conn, graph_name, label_name, label_kind, sample_size=1000):
    query = f"""
        SELECT properties
        FROM {validated_graph_name}.{validated_label_name}
        LIMIT %(limit)s
    """
    rows = await db_conn.execute_query(query, {"limit": sample_size})
    
    # Collect unique property keys
    property_keys: Set[str] = set()
    for row in rows:
        properties = row.get("properties", {})
        if isinstance(properties, dict):
            property_keys.update(properties.keys())
    
    return sorted(list(property_keys))
```

### Optimized Implementation

#### Option 1: Use PostgreSQL JSONB Key Extraction
```python
async def discover_properties_optimized(
    db_conn: DatabaseConnection,
    graph_name: str,
    label_name: str,
    label_kind: str,
) -> List[str]:
    """
    Discover properties using PostgreSQL's JSONB functions.
    
    Uses jsonb_object_keys() to extract all unique keys efficiently.
    """
    from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
    
    validated_graph = validate_graph_name(graph_name)
    validated_label = validate_label_name(label_name)
    safe_graph = escape_identifier(validated_graph)
    safe_label = escape_identifier(validated_label)
    
    # Use PostgreSQL's jsonb_object_keys to find all property keys
    query = f"""
        SELECT DISTINCT jsonb_object_keys(properties) as prop_key
        FROM {safe_graph}.{safe_label}
        WHERE properties IS NOT NULL
        ORDER BY prop_key
    """
    
    try:
        rows = await db_conn.execute_query(query)
        return [row["prop_key"] for row in rows]
    except Exception as e:
        logger.warning(f"Failed to discover properties: {e}")
        return []
```

**Performance:**
- **Before:** Sample 1000 rows, iterate in Python
- **After:** Single SQL query with PostgreSQL's native JSON functions
- **Improvement:** 5-10x faster, finds ALL properties (not just sampled)

#### Option 2: Caching with Invalidation
```python
from functools import lru_cache
from datetime import datetime, timedelta

class PropertyCache:
    """Cache discovered properties with TTL."""
    
    def __init__(self, ttl_minutes: int = 60):
        self._cache: Dict[str, Tuple[List[str], datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, graph_name: str, label_name: str) -> Optional[List[str]]:
        """Get cached properties if not expired."""
        key = f"{graph_name}.{label_name}"
        if key in self._cache:
            properties, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._ttl:
                return properties
        return None
    
    def set(self, graph_name: str, label_name: str, properties: List[str]) -> None:
        """Cache properties with current timestamp."""
        key = f"{graph_name}.{label_name}"
        self._cache[key] = (properties, datetime.now())
    
    def invalidate(self, graph_name: str, label_name: str = None) -> None:
        """Invalidate cache for graph or specific label."""
        if label_name:
            key = f"{graph_name}.{label_name}"
            self._cache.pop(key, None)
        else:
            # Invalidate all labels for graph
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{graph_name}.")]
            for key in keys_to_remove:
                del self._cache[key]

# Global cache instance
property_cache = PropertyCache(ttl_minutes=60)

async def discover_properties_cached(
    db_conn: DatabaseConnection,
    graph_name: str,
    label_name: str,
    label_kind: str,
) -> List[str]:
    """Discover properties with caching."""
    # Check cache first
    cached = property_cache.get(graph_name, label_name)
    if cached is not None:
        logger.debug(f"Using cached properties for {graph_name}.{label_name}")
        return cached
    
    # Not cached - discover and cache
    properties = await discover_properties_optimized(db_conn, graph_name, label_name, label_kind)
    property_cache.set(graph_name, label_name, properties)
    return properties
```

**Cache Invalidation Triggers:**
- CSV import adds new properties → invalidate graph cache
- Manual refresh button in UI → invalidate on demand
- TTL expiration (60 minutes default)

---

## Gap #4: Count Estimation Performance

### Current Implementation
Uses `pg_class.reltuples` for estimates (good!), but:
- Estimates can be wildly inaccurate without ANALYZE
- No automatic ANALYZE after imports
- No option for exact counts when needed

### Improvement: Smart Count Strategy

```python
async def get_label_count(
    db_conn: DatabaseConnection,
    graph_name: str,
    label_name: str,
    exact: bool = False,
) -> int:
    """
    Get count for a label with smart strategy.
    
    Args:
        exact: If True, use COUNT(*). If False, use estimate from pg_class.
    """
    from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
    
    validated_graph = validate_graph_name(graph_name)
    validated_label = validate_label_name(label_name)
    
    if exact:
        # Exact count (slow but accurate)
        safe_graph = escape_identifier(validated_graph)
        safe_label = escape_identifier(validated_label)
        query = f"SELECT COUNT(*) as count FROM {safe_graph}.{safe_label}"
        result = await db_conn.execute_scalar(query)
        return int(result) if result else 0
    else:
        # Fast estimate from statistics
        table_name = f"{validated_graph}_{validated_label}"
        query = """
            SELECT reltuples::bigint as estimate
            FROM pg_class
            WHERE relname = %(table_name)s
        """
        result = await db_conn.execute_scalar(query, {"table_name": table_name})
        return int(result) if result else 0

async def analyze_table(
    db_conn: DatabaseConnection,
    graph_name: str,
    label_name: str,
) -> None:
    """Run ANALYZE on a table to update statistics."""
    from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
    
    validated_graph = validate_graph_name(graph_name)
    validated_label = validate_label_name(label_name)
    safe_graph = escape_identifier(validated_graph)
    safe_label = escape_identifier(validated_label)
    
    try:
        await db_conn.execute_query(f"ANALYZE {safe_graph}.{safe_label}")
        logger.info(f"Updated statistics for {safe_graph}.{safe_label}")
    except Exception as e:
        logger.warning(f"Failed to analyze table: {e}")
```

**Usage:**
- After CSV import: `await analyze_table(db_conn, graph, label)`
- In metadata endpoint: Use estimates for speed
- Add `?exact_counts=true` parameter for exact counts when needed

---

## Implementation Checklist

### Phase 1: Index Creation (Week 1)
- [ ] Implement `create_label_indices()` in metadata.py
- [ ] Add automatic index creation to metadata endpoint
- [ ] Create migration script for existing graphs
- [ ] Test index performance improvements
- [ ] Document index strategy

### Phase 2: Query Optimization (Week 1-2)
- [ ] Rewrite meta-graph discovery with single Cypher query
- [ ] Implement property discovery with `jsonb_object_keys()`
- [ ] Add property caching with TTL
- [ ] Test query performance improvements
- [ ] Benchmark before/after on large graphs

### Phase 3: Count Optimization (Week 2)
- [ ] Implement smart count strategy
- [ ] Add ANALYZE trigger after imports
- [ ] Add `exact_counts` query parameter
- [ ] Test count accuracy and performance

### Phase 4: Monitoring (Week 3)
- [ ] Add performance metrics for slow queries
- [ ] Create dashboard for query performance
- [ ] Set up alerts for slow queries (>5s)
- [ ] Document performance best practices

---

## Effort Estimate

| Task | Hours | Priority |
|------|-------|----------|
| Index creation infrastructure | 4 | HIGH |
| Auto-index on metadata request | 2 | HIGH |
| Meta-graph query optimization | 4 | HIGH |
| Property discovery optimization | 3 | MEDIUM |
| Property caching implementation | 3 | MEDIUM |
| Count strategy implementation | 2 | MEDIUM |
| ANALYZE trigger | 1 | MEDIUM |
| Testing & benchmarking | 8 | HIGH |
| Documentation | 3 | MEDIUM |
| **Total** | **30 hours** | |

---

## Success Metrics

### Performance Targets
- Metadata discovery: <500ms for graphs with <100k nodes
- Node lookup by ID: <10ms
- Meta-graph discovery: <1s for any graph size
- Property discovery: <200ms

### Monitoring Queries
```sql
-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE query LIKE '%ag_catalog.cypher%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY idx_scan DESC;
```

---

## References

- [PostgreSQL Index Types](https://www.postgresql.org/docs/current/indexes-types.html)
- [GIN Indices for JSONB](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)
- [Apache AGE Performance Tuning](https://age.apache.org/docs)
- [Query Optimization Best Practices](https://www.postgresql.org/docs/current/performance-tips.html)
