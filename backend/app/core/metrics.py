"""Prometheus metrics collection for observability."""

import time
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    REGISTRY,
)

# HTTP Request Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Query Execution Metrics
query_executions_total = Counter(
    "query_executions_total",
    "Total number of query executions",
    ["graph", "status"],
)

query_execution_duration_seconds = Histogram(
    "query_execution_duration_seconds",
    "Query execution duration in seconds",
    ["graph"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

query_result_rows = Histogram(
    "query_result_rows",
    "Number of rows returned by queries",
    ["graph"],
    buckets=[10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000],
)

# Session Metrics
active_sessions = Gauge(
    "active_sessions",
    "Number of active user sessions",
)

session_creations_total = Counter(
    "session_creations_total",
    "Total number of session creations",
)

session_destructions_total = Counter(
    "session_destructions_total",
    "Total number of session destructions",
)

# Database Connection Metrics
db_connection_attempts_total = Counter(
    "db_connection_attempts_total",
    "Total number of database connection attempts",
    ["status"],
)

active_db_connections = Gauge(
    "active_db_connections",
    "Number of active database connections",
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Cache Metrics
cache_requests_total = Counter(
    "cache_requests_total",
    "Total number of cache requests",
    ["cache_name", "status"], # status: hit, miss
)

# Database Connection Pool Metrics
db_pool_size = Gauge(
    "db_pool_size",
    "Number of connections in the pool",
    ["database", "type"], # type: total, available, in_use
)

# Error Metrics
errors_total = Counter(
    "errors_total",
    "Total number of errors",
    ["error_code", "error_category"],
)

# Graph Operations Metrics
graph_operations_total = Counter(
    "graph_operations_total",
    "Total number of graph operations",
    ["operation", "graph"],
)

# Node/Edge Operations
node_operations_total = Counter(
    "node_operations_total",
    "Total number of node operations",
    ["operation", "graph"],
)

edge_operations_total = Counter(
    "edge_operations_total",
    "Total number of edge operations",
    ["operation", "graph"],
)


class MetricsCollector:
    """Helper class for collecting metrics."""

    @staticmethod
    def record_http_request(method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def record_query_execution(
        graph: str,
        status: str,
        duration: float,
        row_count: Optional[int] = None,
    ):
        """Record query execution metrics."""
        query_executions_total.labels(graph=graph, status=status).inc()
        query_execution_duration_seconds.labels(graph=graph).observe(duration)
        if row_count is not None:
            query_result_rows.labels(graph=graph).observe(row_count)

    @staticmethod
    def record_session_creation():
        """Record session creation."""
        session_creations_total.inc()
        active_sessions.inc()

    @staticmethod
    def record_session_destruction():
        """Record session destruction."""
        session_destructions_total.inc()
        active_sessions.dec()

    @staticmethod
    def record_db_connection_attempt(status: str):
        """Record database connection attempt."""
        db_connection_attempts_total.labels(status=status).inc()
        if status == "success":
            active_db_connections.inc()
        elif status == "disconnect":
            active_db_connections.dec()

    @staticmethod
    def record_db_query(duration: float):
        """Record database query duration."""
        db_query_duration_seconds.observe(duration)

    @staticmethod
    def record_error(error_code: str, error_category: str):
        """Record error occurrence."""
        errors_total.labels(error_code=error_code, error_category=error_category).inc()

    @staticmethod
    def record_graph_operation(operation: str, graph: str):
        """Record graph operation."""
        graph_operations_total.labels(operation=operation, graph=graph).inc()

    @staticmethod
    def record_node_operation(operation: str, graph: str):
        """Record node operation."""
        node_operations_total.labels(operation=operation, graph=graph).inc()

    @staticmethod
    def record_edge_operation(operation: str, graph: str):
        """Record edge operation."""
        edge_operations_total.labels(operation=operation, graph=graph).inc()

    @staticmethod
    def record_cache_request(cache_name: str, status: str):
        """Record cache hit/miss."""
        cache_requests_total.labels(cache_name=cache_name, status=status).inc()

    @staticmethod
    def record_db_pool_stats(database: str, total: int, available: int, in_use: int):
        """Record database pool statistics."""
        db_pool_size.labels(database=database, type="total").set(total)
        db_pool_size.labels(database=database, type="available").set(available)
        db_pool_size.labels(database=database, type="in_use").set(in_use)

    @staticmethod
    def get_metrics() -> bytes:
        """Get Prometheus metrics in text format."""
        return generate_latest(REGISTRY)


# Global instance
metrics = MetricsCollector()


