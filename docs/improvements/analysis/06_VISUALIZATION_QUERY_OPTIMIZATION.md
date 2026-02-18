# Visualization Query Optimization

**Priority:** MEDIUM  
**Effort:** LOW  
**Impact:** Better UX, faster queries

---

## Gap: Post-Query Filtering Instead of Query-Time Limits

### Current Implementation
```python
# Execute query, get all results
raw_rows = await db_conn.execute_query(sql_query, sql_params)

# Extract ALL nodes and edges
graph_elements = AgTypeParser.extract_graph_elements(parsed_rows)

# THEN check if too many for visualization
if len(graph_elements["nodes"]) > settings.max_nodes_for_graph:
    visualization_warning = "Too many nodes for visualization..."
```

**Problem:** Fetches all data, then warns user it's too much

### Recommended: Query-Time LIMIT

```python
# Add LIMIT to Cypher query automatically
def add_visualization_limit(cypher: str, max_nodes: int) -> str:
    """Add LIMIT clause if not present."""
    if "LIMIT" not in cypher.upper():
        return f"{cypher} LIMIT {max_nodes}"
    return cypher

# In execute_query endpoint
if request.for_visualization:
    cypher_with_limit = add_visualization_limit(
        request.cypher, 
        settings.max_nodes_for_graph
    )
```

### Benefits
- Faster queries (only fetch what's needed)
- Lower memory usage
- Better database performance

---

## Effort Estimate: 4 hours
