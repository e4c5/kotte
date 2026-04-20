"""Tests for middleware."""

import asyncio

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import APIException, ErrorCode
from app.core.middleware import (
    MetricsMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)


class TestRequestIDMiddleware:
    """Tests for request ID middleware."""

    @pytest_asyncio.fixture
    async def request_id_client(self):
        """Client backed by app with RequestIDMiddleware enabled."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=10.0,
        ) as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_request_id_generated(self, request_id_client: httpx.AsyncClient):
        """Test that request ID is generated and included in response."""
        response = await request_id_client.get("/ping")
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0

    @pytest.mark.asyncio
    async def test_request_id_preserved(self, request_id_client: httpx.AsyncClient):
        """Test that provided request ID is preserved."""
        response = await request_id_client.get(
            "/ping",
            headers={"X-Request-ID": "test-request-id-123"},
        )
        assert response.headers.get("X-Request-ID") == "test-request-id-123"


class TestCSRFMiddleware:
    """Tests for CSRF middleware (disabled in test app)."""

    @pytest.mark.asyncio
    async def test_csrf_token_endpoint_requires_auth(self, async_client: httpx.AsyncClient):
        """CSRF token endpoint requires session (401 without auth)."""
        response = await async_client.get("/api/v1/auth/csrf-token")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_csrf_protection_disabled_in_test(self, async_client: httpx.AsyncClient):
        """Test app has CSRF disabled, so login works without CSRF token."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_works_without_csrf_when_disabled(self, async_client: httpx.AsyncClient):
        """Login works when CSRF is disabled (test app config)."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware (disabled in test app)."""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_in_test(self, async_client: httpx.AsyncClient):
        """Test app has rate limit disabled; requests are not throttled."""
        # Multiple requests should all succeed (no 429)
        for _ in range(5):
            response = await async_client.get("/api/v1/auth/me")
            assert response.status_code == 401  # No auth, but not 429


def _make_request(*, session: dict | None = None, client_ip: str = "127.0.0.1") -> Request:
    """Build a ``Request`` whose scope mirrors what SessionMiddleware would set.

    Unit-testing ``RateLimitMiddleware.dispatch`` directly avoids a known
    Starlette gotcha where exceptions raised from a ``BaseHTTPMiddleware``
    don't always reach FastAPI's registered exception handlers, so an
    end-to-end HTTP test would tell us about FastAPI's exception plumbing
    rather than about the rate-limit logic we actually care about here.
    """
    scope: dict = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/x",
        "raw_path": b"/x",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    if session is not None:
        scope["session"] = session
    return Request(scope)


class TestRateLimitPerUser:
    """The per-user rate limit must fire when a session_id in the signed
    cookie maps to a known user in session_manager. Regression coverage for
    the fact that the middleware used to read user_id directly off the
    cookie session, which never contained it -- so the per-user branch was
    unreachable and ``rate_limit_per_user`` was dead config.
    """

    @pytest_asyncio.fixture
    async def per_user_dispatch(self, monkeypatch):
        """Yield a ``call(request)`` helper that drives ``RateLimitMiddleware.dispatch``.

        IP limit is set very high so the per-user branch is the one that
        fires; otherwise the IP cap would mask the bug we're guarding
        against.

        We monkeypatch ``settings`` via ``app.core.middleware``'s own
        namespace rather than reimporting from ``app.core.config``: the
        ``test_app`` conftest fixture does ``del sys.modules["app.core.config"]``
        between tests, which spawns a *new* ``settings`` instance, but
        ``app.core.middleware`` still holds its original module-load
        reference. Patching via the middleware module guarantees we're
        modifying the same object the middleware reads at runtime.
        """
        from app.core import middleware as mw_module

        monkeypatch.setattr(mw_module.settings, "rate_limit_enabled", True)
        monkeypatch.setattr(mw_module.settings, "rate_limit_per_minute", 10_000)
        monkeypatch.setattr(mw_module.settings, "rate_limit_per_user", 2)

        async def call_next(_request):
            # BaseHTTPMiddleware.dispatch awaits the result of call_next, so
            # the callable must be async-shaped. Yield to the loop once so
            # we satisfy the async contract honestly rather than declaring
            # `async` for shape only.
            await asyncio.sleep(0)
            return JSONResponse({"ok": True})

        async def noop_app(scope, receive, send):
            """Intentionally empty ASGI app stub.

            ``BaseHTTPMiddleware.__init__`` requires an ``app`` callable, but
            these tests drive ``dispatch`` directly so the inner app is never
            actually invoked. Kept as a placeholder solely to satisfy the
            constructor signature.
            """

        middleware = RateLimitMiddleware(noop_app)

        async def call(request):
            return await middleware.dispatch(request, call_next)

        yield call

    @pytest.mark.asyncio
    async def test_per_user_rate_limit_raises_429_after_n_calls(self, per_user_dispatch):
        """rate_limit_per_user + 1 calls → final call raises APIException(429).

        Without the fix the middleware reads ``user_id`` from the cookie
        session (which never holds it), keeps ``user_id = None``, and
        therefore never enters the per-user branch -- all 3 calls succeed
        and the cap is silently unreachable.
        """
        from app.core.auth import session_manager

        sid = session_manager.create_session(user_id="rate-limit-test-user")
        session = {"session_id": sid}

        r1 = await per_user_dispatch(_make_request(session=session))
        assert r1.status_code == 200
        r2 = await per_user_dispatch(_make_request(session=session))
        assert r2.status_code == 200
        with pytest.raises(APIException) as exc_info:
            await per_user_dispatch(_make_request(session=session))
        assert exc_info.value.status_code == 429
        assert exc_info.value.code == ErrorCode.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_per_user_buckets_are_independent(self, per_user_dispatch):
        """User A hitting their cap must not throttle User B."""
        from app.core.auth import session_manager

        sid_a = session_manager.create_session(user_id="user-a")
        sid_b = session_manager.create_session(user_id="user-b")

        for _ in range(2):
            assert (
                await per_user_dispatch(_make_request(session={"session_id": sid_a}))
            ).status_code == 200
        with pytest.raises(APIException) as exc_a:
            await per_user_dispatch(_make_request(session={"session_id": sid_a}))
        assert exc_a.value.status_code == 429

        for _ in range(2):
            assert (
                await per_user_dispatch(_make_request(session={"session_id": sid_b}))
            ).status_code == 200
        with pytest.raises(APIException) as exc_b:
            await per_user_dispatch(_make_request(session={"session_id": sid_b}))
        assert exc_b.value.status_code == 429

    @pytest.mark.asyncio
    async def test_unknown_session_id_does_not_enforce_per_user_quota(self, per_user_dispatch):
        """If the cookie carries a session_id that session_manager doesn't know
        (e.g. backend restarted, session expired and was purged), the per-user
        branch must stay dormant rather than wrongly bucketing all such
        traffic under a single empty key. Only the IP cap applies.
        """
        session = {"session_id": "session-id-that-was-never-registered"}
        for _ in range(5):
            resp = await per_user_dispatch(_make_request(session=session))
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_session_in_scope_does_not_enforce_per_user_quota(self, per_user_dispatch):
        """Anonymous traffic (no session in scope at all) must skip the
        per-user check entirely. Only the IP cap applies.
        """
        for _ in range(5):
            resp = await per_user_dispatch(_make_request(session=None))
            assert resp.status_code == 200


class TestMetricsMiddleware:
    """Regression coverage for ``MetricsMiddleware.dispatch``.

    The middleware must record a Prometheus sample for every request that
    flows through it, including the error paths. The critical regression
    guarded here is cancellation: ``asyncio.CancelledError`` inherits from
    ``BaseException``, not ``Exception``, so a previous ``except Exception``
    branch skipped setting ``status_code`` and the ``finally`` clause then
    blew up with ``UnboundLocalError``, masking the cancellation.
    """

    @pytest_asyncio.fixture
    async def record_calls(self, monkeypatch):
        """Capture every ``metrics.record_http_request`` call on the
        same module reference the middleware uses.

        We patch on ``app.core.middleware.metrics`` rather than
        ``app.core.metrics.metrics`` so the stub is visible to
        ``MetricsMiddleware.dispatch`` regardless of how the test
        conftest has or hasn't reimported ``app.core.metrics``.
        """
        from app.core import middleware as mw_module

        calls: list[tuple[str, str, int, float]] = []

        def fake_record(method, endpoint, status_code, duration):
            calls.append((method, endpoint, status_code, duration))

        monkeypatch.setattr(mw_module.metrics, "record_http_request", fake_record)
        return calls

    @pytest_asyncio.fixture
    async def metrics_dispatch(self):
        """Return ``call(call_next, path="/x")`` which drives
        ``MetricsMiddleware.dispatch`` directly with a stub ASGI app.

        Driving ``dispatch`` directly (instead of through ``httpx``) keeps
        the test honest about which exception type propagates out of the
        middleware. Going through ``BaseHTTPMiddleware``'s ASGI wrapper
        can swallow/convert ``CancelledError`` via the outer anyio task
        group, which is exactly the plumbing we're not trying to test
        here -- we're testing that ``dispatch`` itself doesn't raise
        ``UnboundLocalError`` on the cancellation path.
        """

        async def noop_app(scope, receive, send):
            """Placeholder ASGI app; tests drive ``dispatch`` directly."""

        middleware = MetricsMiddleware(noop_app)

        async def call(call_next, path: str = "/x"):
            request = _make_request_path(path)
            return await middleware.dispatch(request, call_next)

        return call

    @pytest.mark.asyncio
    async def test_happy_path_records_response_status(self, metrics_dispatch, record_calls):
        async def call_next(_request):
            await asyncio.sleep(0)
            return JSONResponse({"ok": True}, status_code=201)

        response = await metrics_dispatch(call_next, path="/x")

        assert response.status_code == 201
        assert len(record_calls) == 1
        method, endpoint, status_code, duration = record_calls[0]
        assert method == "GET"
        assert endpoint == "/x"
        assert status_code == 201
        assert duration >= 0.0

    @pytest.mark.asyncio
    async def test_exception_path_records_500_and_reraises(self, metrics_dispatch, record_calls):
        """``Exception`` subclass from ``call_next`` must propagate, and
        we must still record a 500 sample in ``finally``.
        """

        async def call_next(_request):
            await asyncio.sleep(0)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await metrics_dispatch(call_next, path="/x")

        assert len(record_calls) == 1
        _method, _endpoint, status_code, _duration = record_calls[0]
        assert status_code == 500

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_without_unbound_local(
        self, metrics_dispatch, record_calls
    ):
        """Regression: ``asyncio.CancelledError`` (a ``BaseException``) must
        propagate out cleanly and the ``finally`` block must still record a
        500 sample. Before the fix this path raised ``UnboundLocalError``
        because ``status_code`` was never assigned.
        """

        async def call_next(_request):
            await asyncio.sleep(0)
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await metrics_dispatch(call_next, path="/x")

        assert len(record_calls) == 1
        _method, _endpoint, status_code, _duration = record_calls[0]
        assert status_code == 500

    @pytest.mark.asyncio
    async def test_metrics_endpoint_is_short_circuited(self, metrics_dispatch, record_calls):
        """Both ``/metrics`` and ``/api/v1/metrics`` must bypass the
        metrics bookkeeping -- scraping the metrics endpoint itself must
        not record a sample (otherwise a Prometheus scrape would perturb
        its own counters).
        """
        hits = 0

        async def call_next(_request):
            nonlocal hits
            hits += 1
            await asyncio.sleep(0)
            return JSONResponse({"ok": True})

        await metrics_dispatch(call_next, path="/metrics")
        await metrics_dispatch(call_next, path="/api/v1/metrics")

        assert hits == 2
        assert record_calls == []


def _make_request_path(path: str) -> Request:
    """Build a minimal ``Request`` whose path matches ``path``.

    Separate from ``_make_request`` above because the rate-limit tests
    care about ``session`` / ``client`` fields, while the metrics tests
    only care about ``path``.
    """
    scope: dict = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    return Request(scope)
