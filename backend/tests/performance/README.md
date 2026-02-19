# Performance Tests

Benchmark tests for the Kotte backend. These tests require a PostgreSQL/AGE database with representative data to produce meaningful results.

## Prerequisites

- PostgreSQL 14+ with Apache AGE extension
- Test database with graphs containing 10k+ nodes for basic benchmarks, 100k+ for full benchmarks

## Running Benchmarks

```bash
cd backend
. venv/bin/activate

# Set environment for test database
export USE_REAL_TEST_DB=true
export TEST_DB_HOST=localhost
export TEST_DB_PORT=5432
export TEST_DB_NAME=your_db
export TEST_DB_USER=your_user
export TEST_DB_PASSWORD=your_password

# Run performance tests
pytest tests/performance/ -v -s

# Run only performance tests (exclude if not configured)
pytest -m performance -v -s
```

## Expected Metrics

From `docs/PERFORMANCE.md` and analysis documents:

| Operation | Target | Notes |
|-----------|--------|-------|
| Metadata discovery | <500ms | For graphs with <100k nodes |
| Node lookup by ID | <10ms | With indices (was 250ms without) |
| Meta-graph discovery | <1s | For any graph size |
| Import speed | >1000 rows/s | With batch insertion |

## Skipped Without Real DB

When `USE_REAL_TEST_DB` is not set, performance tests are skipped. Set up a test database and configure the environment to run them.
