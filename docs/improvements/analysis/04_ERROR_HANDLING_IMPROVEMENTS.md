# Error Handling Improvements

**Priority:** MEDIUM  
**Effort:** MEDIUM  
**Impact:** Better debugging, user experience

---

## Overview

Current error handling uses generic exceptions that don't distinguish between different graph operation failures. This makes debugging difficult and provides poor user feedback.

---

## Gap #1: Generic Exception Handling

### Current Pattern
```python
except Exception as e:
    logger.exception("Error getting metadata")
    raise APIException(
        code=ErrorCode.DB_UNAVAILABLE,
        message=f"Failed to get graph metadata: {str(e)}",
        ...
    )
```

**Problems:**
- All database errors treated the same
- No distinction between constraint violations, syntax errors, missing resources
- User gets generic "DB_UNAVAILABLE" for different root causes

---

## Recommended: Graph-Specific Exception Types

### Implementation

```python
# backend/app/core/errors.py

class GraphConstraintViolation(APIException):
    """Raised when graph constraint is violated."""
    def __init__(self, constraint_type: str, details: str):
        super().__init__(
            code=ErrorCode.GRAPH_CONSTRAINT_VIOLATION,
            message=f"{constraint_type} constraint violated: {details}",
            category=ErrorCategory.VALIDATION,
            status_code=422,
        )

class GraphNodeNotFound(APIException):
    """Raised when referenced node doesn't exist."""
    def __init__(self, node_id: str, graph: str):
        super().__init__(
            code=ErrorCode.NODE_NOT_FOUND,
            message=f"Node {node_id} not found in graph '{graph}'",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )

class GraphEdgeNotFound(APIException):
    """Raised when referenced edge doesn't exist."""
    def __init__(self, edge_id: str, graph: str):
        super().__init__(
            code=ErrorCode.EDGE_NOT_FOUND,
            message=f"Edge {edge_id} not found in graph '{graph}'",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )

class GraphCypherSyntaxError(APIException):
    """Raised when Cypher query has syntax errors."""
    def __init__(self, query: str, error_message: str):
        super().__init__(
            code=ErrorCode.CYPHER_SYNTAX_ERROR,
            message=f"Cypher syntax error: {error_message}",
            category=ErrorCategory.VALIDATION,
            status_code=422,
            details={"query": query[:200], "error": error_message},
        )
```

### Usage Example

```python
# backend/app/api/v1/graph.py

try:
    result = await db_conn.execute_query(cypher_query, params)
except psycopg.errors.UniqueViolation as e:
    raise GraphConstraintViolation("unique", str(e))
except psycopg.errors.ForeignKeyViolation as e:
    raise GraphConstraintViolation("referential integrity", str(e))
except psycopg.errors.SyntaxError as e:
    raise GraphCypherSyntaxError(cypher_query, str(e))
except Exception as e:
    logger.exception("Unexpected graph operation error")
    raise APIException(
        code=ErrorCode.DB_UNAVAILABLE,
        message=f"Graph operation failed: {str(e)}",
        category=ErrorCategory.UPSTREAM,
        status_code=500,
    )
```

---

## Gap #2: No Error Context for Debugging

### Improvement: Structured Error Details

```python
# Add query context to errors
raise APIException(
    code=ErrorCode.QUERY_EXECUTION_ERROR,
    message=f"Query failed: {error_msg}",
    category=ErrorCategory.UPSTREAM,
    status_code=500,
    details={
        "query": query[:500],
        "graph": graph_name,
        "line": error_line,  # Parse from PostgreSQL error
        "hint": error_hint,  # PostgreSQL hint field
        "parameters": {k: str(v)[:100] for k, v in params.items()},
    }
)
```

---

## Gap #3: No User-Friendly Error Messages

### Current
```
"Failed to get graph metadata: syntax error at or near ')'"
```

### Improved
```
"Invalid Cypher query syntax near line 3: missing closing parenthesis. 
Check that all MATCH clauses are properly closed.
Query: MATCH (n:Person WHERE id(n) = 123..."
```

### Implementation

```python
def format_cypher_error(error: str, query: str) -> str:
    """Convert PostgreSQL error to user-friendly Cypher error."""
    
    patterns = {
        r"syntax error at or near": "Syntax error near",
        r"column .* does not exist": "Property does not exist",
        r"relation .* does not exist": "Label does not exist",
    }
    
    user_message = error
    for pattern, replacement in patterns.items():
        user_message = re.sub(pattern, replacement, user_message)
    
    # Extract line number if available
    line_match = re.search(r"LINE (\d+):", error)
    if line_match:
        line_num = int(line_match.group(1))
        query_lines = query.split('\n')
        if line_num <= len(query_lines):
            user_message += f"\nAt: {query_lines[line_num-1].strip()}"
    
    return user_message
```

---

## Implementation Checklist

- [ ] Create graph-specific exception classes
- [ ] Add constraint violation detection
- [ ] Add syntax error parsing and formatting
- [ ] Add structured error details
- [ ] Update all endpoints to use specific exceptions
- [ ] Add error context to logs
- [ ] Test error message clarity

---

## Effort Estimate: 16 hours

---

## References

- [PostgreSQL Error Codes](https://www.postgresql.org/docs/current/errcodes-appendix.html)
- [FastAPI Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
