# Security Gaps and SQL Injection Risks

**Priority:** HIGH  
**Effort:** LOW  
**Risk:** HIGH (Data breach, SQL injection)

---

## Overview

While the codebase demonstrates strong security foundations with parameterized queries and validation layers, **three critical security gaps** exist that create SQL injection vulnerabilities if the validation layer is bypassed or fails.

---

## Gap #1: Unvalidated Graph Name in `get_meta_graph()`

### Location
**File:** `backend/app/api/v1/graph.py`  
**Lines:** 221-229

### Current Code
```python
@router.get("/{graph_name}/meta-graph", response_model=MetaGraphResponse)
async def get_meta_graph(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    try:
        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": graph_name}  # ← PROBLEM: Not validated
        )
```

### Issue
The `graph_name` parameter from the URL path is used **directly in the database query** without validation. While the query uses parameterization (which prevents basic SQL injection), validation at line 315 happens **after** the database query.

### Inconsistency
All other endpoints in the same file validate graph names **before** use:
- Line 81: `validated_graph_name = validate_graph_name(graph_name)` (in `get_graph_metadata`)
- Line 344: `validated_graph_name = validate_graph_name(graph_name)` (in `expand_node_neighborhood`)

### Attack Vector
While parameterized queries prevent classic SQL injection, an attacker could:
1. Provide malformed graph names that break query logic
2. Exploit edge cases in PostgreSQL identifier handling
3. Bypass later validation if code paths change

### Fix
```python
@router.get("/{graph_name}/meta-graph", response_model=MetaGraphResponse)
async def get_meta_graph(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    try:
        # FIXED: Validate graph name before use
        validated_graph_name = validate_graph_name(graph_name)
        
        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": validated_graph_name}  # ← Now uses validated name
        )
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{validated_graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )
```

### Testing
```python
# Test case: Ensure validation happens before DB query
async def test_meta_graph_validates_graph_name():
    # Invalid graph name with SQL injection attempt
    invalid_name = "'; DROP TABLE users; --"
    
    response = await client.get(f"/api/v1/graphs/{invalid_name}/meta-graph")
    
    # Should return 422 Unprocessable Entity (validation error)
    assert response.status_code == 422
    assert "Invalid graph name" in response.json()["error"]["message"]
```

---

## Gap #2: F-String Table Names Without Escaping

### Location
**Files:**
- `backend/app/services/metadata.py` (lines 45-56, 103-106, 145-157)
- `backend/app/api/v1/graph.py` (lines 272-278)

### Current Code
```python
# metadata.py, line 45-56
def discover_properties(db_conn, graph_name, label_name, label_kind, sample_size=1000):
    validated_graph_name = validate_graph_name(graph_name)
    validated_label_name = validate_label_name(label_name)
    
    # PROBLEM: F-string with validated names (risky pattern)
    query = f"""
        SELECT properties
        FROM {validated_graph_name}.{validated_label_name}
        LIMIT %(limit)s
    """
    rows = await db_conn.execute_query(query, {"limit": sample_size})
```

### Issue
While `validated_graph_name` and `validated_label_name` **are validated** using regex patterns, this creates a **dangerous pattern**:

1. **Reliance on validation layer**: If validation is bypassed (e.g., internal calls, refactoring errors), injection is possible
2. **Mixed patterns**: Combines parameterized queries (`%(limit)s`) with f-strings, creating inconsistency
3. **Difficult to audit**: Security reviewers cannot easily verify safety without tracing validation
4. **PostgreSQL quirks**: Even validated identifiers can cause issues with special characters in specific contexts

### Attack Scenario
```python
# If validation is accidentally bypassed in a refactor:
graph_name = "my_graph; DROP TABLE important_data; --"
# F-string would execute: 
# SELECT properties FROM my_graph; DROP TABLE important_data; --.label_name LIMIT 1000
```

### Best Practice: PostgreSQL Identifier Escaping
PostgreSQL provides `quote_ident()` for safe identifier handling. We should implement a Python equivalent.

### Fix: Implement `escape_identifier()` Utility

**Step 1:** Add to `backend/app/core/validation.py`
```python
def escape_identifier(identifier: str) -> str:
    """
    Escape a PostgreSQL identifier using quote_ident logic.
    
    This provides defense-in-depth even when identifiers are validated.
    PostgreSQL identifiers are escaped by:
    1. Wrapping in double quotes
    2. Doubling any internal double quotes
    
    Args:
        identifier: Validated PostgreSQL identifier
        
    Returns:
        Safely escaped identifier
        
    Example:
        >>> escape_identifier('my_graph')
        '"my_graph"'
        >>> escape_identifier('my"graph')
        '"my""graph"'
    """
    # Replace " with ""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
```

**Step 2:** Apply to metadata queries
```python
# metadata.py, line 45-56 (FIXED)
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier

async def discover_properties(db_conn, graph_name, label_name, label_kind, sample_size=1000):
    validated_graph_name = validate_graph_name(graph_name)
    validated_label_name = validate_label_name(label_name)
    
    # FIXED: Escape identifiers for defense-in-depth
    safe_graph = escape_identifier(validated_graph_name)
    safe_label = escape_identifier(validated_label_name)
    
    query = f"""
        SELECT properties
        FROM {safe_graph}.{safe_label}
        LIMIT %(limit)s
    """
    rows = await db_conn.execute_query(query, {"limit": sample_size})
```

**Step 3:** Apply to graph.py
```python
# graph.py, line 272-278 (FIXED)
validated_edge_label = validate_label_name(edge_label)
safe_graph = escape_identifier(validated_graph_name)
safe_edge = escape_identifier(validated_edge_label)

sample_query = f"""
    SELECT start_id, end_id
    FROM {safe_graph}.{safe_edge}
    LIMIT 100
"""
samples = await db_conn.execute_query(sample_query)
```

### Alternative: Use Information Schema Queries
For some queries, avoid f-strings entirely by querying `information_schema`:

```python
# Instead of: SELECT properties FROM {graph}.{label}
# Use information schema:
query = """
    SELECT c.column_name, t.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables t ON c.table_name = t.table_name
    WHERE t.table_schema = %(schema)s 
      AND t.table_name = %(table)s
"""
params = {"schema": validated_graph_name, "table": validated_label_name}
```

### Testing
```python
# Test escape_identifier
def test_escape_identifier():
    # Basic identifier
    assert escape_identifier("my_graph") == '"my_graph"'
    
    # Identifier with quotes
    assert escape_identifier('my"graph') == '"my""graph"'
    
    # Identifier with multiple quotes
    assert escape_identifier('my""graph') == '"my""""graph"'
    
    # Ensure it prevents injection
    malicious = 'test; DROP TABLE users; --'
    escaped = escape_identifier(malicious)
    # Should be: "test; DROP TABLE users; --"
    # When used in query, treated as single identifier
```

---

## Gap #3: CSV Import String Interpolation

### Location
**File:** `backend/app/api/v1/import_csv.py`  
**Lines:** 72-73, 143-144

### Current Code
```python
# Line 72-73
validated_graph_name = validate_graph_name(request.graph)
create_graph_query = f"""
    SELECT * FROM ag_catalog.create_graph('{validated_graph_name}')
"""

# Line 143-144
create_label_query = f"""
    SELECT * FROM ag_catalog.create_vlabel('{validated_graph_name}', '{validated_label}')
"""
```

### Issue
Apache AGE administrative functions (`create_graph`, `create_vlabel`) don't support parameterized queries, forcing string interpolation. However:

1. Uses single quotes (') which are the SQL string delimiter - should use escaping
2. Doesn't use `escape_identifier()` for consistency
3. Lacks defensive comment explaining why interpolation is necessary

### Fix
```python
from app.core.validation import validate_graph_name, escape_identifier

# Line 72-73 (FIXED)
validated_graph_name = validate_graph_name(request.graph)
safe_graph = escape_identifier(validated_graph_name)

# Note: create_graph() doesn't support parameterization; validated names prevent injection
create_graph_query = f"""
    SELECT * FROM ag_catalog.create_graph({safe_graph})
"""

# Line 143-144 (FIXED)
validated_label = validate_label_name(request.vertex_label)
safe_graph = escape_identifier(validated_graph_name)
safe_label = escape_identifier(validated_label)

# Note: create_vlabel() doesn't support parameterization; validated + escaped names prevent injection
create_label_query = f"""
    SELECT * FROM ag_catalog.create_vlabel({safe_graph}, {safe_label})
"""
```

### Testing
```python
async def test_csv_import_validates_graph_name():
    # Attempt injection via graph name
    malicious_csv = "name,age\nAlice,30"
    
    response = await client.post(
        "/api/v1/import/csv",
        data={
            "graph": "test'; DROP TABLE users; --",
            "vertex_label": "Person",
        },
        files={"file": ("test.csv", malicious_csv, "text/csv")}
    )
    
    # Should return 422 due to validation failure
    assert response.status_code == 422
```

---

## Implementation Checklist

### Phase 1: Critical Fixes (Immediate)
- [ ] Add `validate_graph_name()` at line 221 in `graph.py`
- [ ] Implement `escape_identifier()` in `validation.py`
- [ ] Apply `escape_identifier()` to all metadata queries (metadata.py lines 45, 103, 145)
- [ ] Apply `escape_identifier()` to graph.py line 272
- [ ] Apply `escape_identifier()` to import_csv.py lines 72, 143
- [ ] Add defensive comments explaining why f-strings are used

### Phase 2: Testing (Same Sprint)
- [ ] Unit tests for `escape_identifier()`
- [ ] Integration test for unvalidated graph name scenario
- [ ] Security test for SQL injection attempts via graph/label names
- [ ] Test CSV import with malicious graph names

### Phase 3: Code Review (Before Merge)
- [ ] Security review of all f-string database queries
- [ ] Verify all endpoints validate inputs before use
- [ ] Audit for any remaining string interpolation patterns
- [ ] Document security patterns in SECURITY.md

---

## Additional Security Recommendations

### 1. Automated Security Scanning
Add to CI/CD pipeline:
```yaml
# .github/workflows/security.yml
- name: SQL Injection Scan
  run: |
    # Detect f-strings in database queries
    grep -r "f\".*FROM.*{" backend/app/ && exit 1 || exit 0
    grep -r "f'.*FROM.*{" backend/app/ && exit 1 || exit 0
```

### 2. Pre-commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash
# Warn about f-strings in database queries
if git diff --cached --name-only | grep -q "\.py$"; then
    if git diff --cached | grep -q "f[\"'].*FROM.*{"; then
        echo "WARNING: F-string detected in database query"
        echo "Ensure validation + escaping are applied"
    fi
fi
```

### 3. Linting Rule
Add to `.pylintrc`:
```ini
[MESSAGES CONTROL]
# Custom rule: Ban f-strings with SQL keywords
disable=C0301,C0103
enable=security-sql-injection-fstring
```

---

## Effort Estimate

| Task | Hours | Priority |
|------|-------|----------|
| Implement `escape_identifier()` | 1 | HIGH |
| Fix `graph.py` line 221 | 0.5 | HIGH |
| Apply to metadata.py (3 locations) | 1 | HIGH |
| Apply to graph.py line 272 | 0.5 | HIGH |
| Apply to import_csv.py (2 locations) | 1 | MEDIUM |
| Write unit tests | 2 | HIGH |
| Write integration tests | 2 | HIGH |
| Security review | 2 | HIGH |
| **Total** | **10 hours** | |

---

## References

- [PostgreSQL Identifier Syntax](https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS)
- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [Apache AGE Security Best Practices](https://age.apache.org/docs)
- [psycopg3 Query Parameters](https://www.psycopg.org/psycopg3/docs/basic/params.html)
