"""Prometheus metrics collection for observability."""

import threading
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
)

# Query Execution Metrics
query_executions_total = Counter(
    "query_executions_total",
    "Total number of Cypher query executions",
    ["graph", "status"],  # status: success, error
)

query_execution_duration_seconds = Histogram(
    "query_execution_duration_seconds",
    "Cypher query execution duration in seconds",
    ["graph"],
)

query_result_rows = Histogram(
    "query_result_rows",
    "Number of rows returned by Cypher queries",
    ["graph"],
    buckets=[0, 1, 10, 50, 100, 500, 1000, 5000, 10000, float("inf")],
)

# Session Metrics
session_creations_total = Counter(
    "session_creations_total",
    "Total number of sessions created",
)

session_destructions_total = Counter(
    "session_destructions_total",
    "Total number of sessions destroyed",
)

active_sessions = Gauge(
    "active_sessions",
    "Number of currently active sessions",
)

# Database Connection Metrics
db_connection_attempts_total = Counter(
    "db_connection_attempts_total",
    "Total number of database connection attempts",
    ["status"],  # status: success, failure, disconnect
)

active_db_connections = Gauge(
    "active_db_connections",
    "Number of currently active database connections",
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf")],
)

# Cache Metrics
cache_requests_total = Counter(
    "cache_requests_total",
    "Total number of cache requests",
    ["cache_name", "status"],  # status: hit, miss
)

# Database Connection Pool Metrics
db_pool_size = Gauge(
    "db_pool_size",
    "Number of connections in the pool",
    # Second label is pool metric kind: total | available | in_use
    ["database", "type"],
)

# Error Metrics
errors_total = Counter(
    "errors_total",
    "Total number of errors",
    ["error_code", "error_category"],
)

# Graph Operation Metrics
graph_operations_total = Counter(
    "graph_operations_total",
    "Total number of graph operations",
    ["operation", "graph"],
)

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

    def __init__(self):
        self._known_graphs = set()
        self._known_databases = set()
        self._max_labels = 100  # Maximum unique labels for graphs/databases to prevent explosion
        self._lock = threading.Lock()

    def _sanitize_graph(self, graph: str) -> str:
        """Limit cardinality of graph labels. Thread-safe."""
        with self._lock:
            if graph in self._known_graphs:
                return graph
            if len(self._known_graphs) >= self._max_labels:
                return "other"
            self._known_graphs.add(graph)
            return graph

    def _sanitize_database(self, database: str) -> str:
        """Limit cardinality of database labels. Thread-safe."""
        with self._lock:
            if database in self._known_databases:
                return database
            if len(self._known_databases) >= self._max_labels:
                return "other"
            self._known_databases.add(database)
            return database

    def record_http_request(
        self, method: str, endpoint: str, status_code: int, duration: float
    ) -> None:
        """Record HTTP request metrics."""
        http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    def record_query_execution(
        self,
        graph: str,
        status: str,
        duration: float,
        row_count: Optional[int] = None,
    ) -> None:
        """Record query execution metrics."""
        safe_graph = self._sanitize_graph(graph)
        query_executions_total.labels(graph=safe_graph, status=status).inc()
        query_execution_duration_seconds.labels(graph=safe_graph).observe(duration)
        if row_count is not None:
            query_result_rows.labels(graph=safe_graph).observe(row_count)

    @staticmethod
    def record_session_creation() -> None:
        """Record session creation."""
        session_creations_total.inc()
        active_sessions.inc()

    @staticmethod
    def record_session_destruction() -> None:
        """Record session destruction."""
        session_destructions_total.inc()
        active_sessions.dec()

    @staticmethod
    def record_db_connection_attempt(status: str) -> None:
        """Record database connection attempt."""
        db_connection_attempts_total.labels(status=status).inc()
        if status == "success":
            active_db_connections.inc()
        elif status == "disconnect":
            active_db_connections.dec()

    @staticmethod
    def record_db_query(duration: float) -> None:
        """Record database query duration."""
        db_query_duration_seconds.observe(duration)

    @staticmethod
    def record_error(error_code: str, error_category: str) -> None:
        """Record error occurrence."""
        errors_total.labels(error_code=error_code, error_category=error_category).inc()

    def record_graph_operation(self, operation: str, graph: str) -> None:
        """Record graph operation."""
        safe_graph = self._sanitize_graph(graph)
        graph_operations_total.labels(operation=operation, graph=safe_graph).inc()

    def record_node_operation(self, operation: str, graph: str) -> None:
        """Record node operation."""
        safe_graph = self._sanitize_graph(graph)
        node_operations_total.labels(operation=operation, graph=safe_graph).inc()

    def record_edge_operation(self, operation: str, graph: str) -> None:
        """Record edge operation."""
        safe_graph = self._sanitize_graph(graph)
        edge_operations_total.labels(operation=operation, graph=safe_graph).inc()

    @staticmethod
    def record_cache_request(cache_name: str, status: str) -> None:
        """Record cache hit/miss."""
        cache_requests_total.labels(cache_name=cache_name, status=status).inc()

    def record_db_pool_stats(self, database: str, total: int, available: int, in_use: int) -> None:
        """Record database pool statistics."""
        safe_db = self._sanitize_database(database)
        db_pool_size.labels(database=safe_db, type="total").set(total)
        db_pool_size.labels(database=safe_db, type="available").set(available)
        db_pool_size.labels(database=safe_db, type="in_use").set(in_use)

    @staticmethod
    def get_metrics() -> bytes:
        """Get Prometheus metrics in text format."""
        return generate_latest(REGISTRY)


# Global instance
metrics = MetricsCollector()
