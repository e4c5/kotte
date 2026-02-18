# Path Handling Improvements

**Priority:** LOW  
**Effort:** MEDIUM  
**Impact:** Better path query support

---

## Gap: Paths Flattened to Nodes and Edges

### Current Implementation
```python
# Path extracted as separate nodes and edges
# Path semantics lost
for element in path:
    if element["type"] == "node":
        nodes.append(element)
    elif element["type"] == "edge":
        edges.append(element)
```

**Problem:** Cannot reconstruct original path from results

### Recommended: Preserve Path Structure

```python
{
    "type": "path",
    "segments": [
        {"node": {...}, "edge": {...}, "node": {...}},
        ...
    ],
    "length": 3,
    "start_node_id": "123",
    "end_node_id": "456"
}
```

### Benefits
- Path-based visualizations
- Maintain traversal order
- Support path-specific operations

---

## Effort Estimate: 12 hours
