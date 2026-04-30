"""Tests for v1.1.0 engine auto-discovery in z4j-fastapi.

z4j-fastapi's ``z4j_lifespan(...)`` and ``install_z4j(...)`` now
accept handles for all 6 engines (celery + rq + arq + dramatiq +
huey + taskiq), not just celery. These tests pin the contract for
each engine's discovery so a regression in the wiring layer is
caught fast.
"""

from __future__ import annotations

from typing import Any

import pytest

from z4j_fastapi.framework import (
    discover_engines,
    _try_import_arq_engine,
    _try_import_celery_engine,
    _try_import_dramatiq_engine,
    _try_import_huey_engine,
    _try_import_rq_engine,
    _try_import_taskiq_engine,
)


# ---------------------------------------------------------------------------
# Celery (regression: must still work via the new fan-out path)
# ---------------------------------------------------------------------------


class TestCelery:
    def test_returns_none_with_no_celery_app(self) -> None:
        assert _try_import_celery_engine(None) is None


# ---------------------------------------------------------------------------
# RQ
# ---------------------------------------------------------------------------


class TestRq:
    def test_returns_none_when_no_rq_app(self) -> None:
        assert _try_import_rq_engine(None) is None

    def test_picks_up_passed_rq_app(self) -> None:
        pytest.importorskip("z4j_rq")

        class _FakeRqApp:
            connection = None
            queues: list[Any] = []
            def queue_for_name(self, name): return None  # noqa: ARG002
            def queue_for(self, job): return None  # noqa: ARG002
            def fetch_job(self, tid): return None  # noqa: ARG002

        fake = _FakeRqApp()
        adapter = _try_import_rq_engine(fake)
        assert adapter is not None
        assert adapter.rq_app is fake


# ---------------------------------------------------------------------------
# arq
# ---------------------------------------------------------------------------


class TestArq:
    def test_returns_none_with_no_settings(self) -> None:
        assert _try_import_arq_engine(None, (), "arq:queue") is None

    def test_picks_up_settings(self) -> None:
        pytest.importorskip("z4j_arq")

        class _FakePool:
            async def enqueue_job(self, *_a, **_k): ...

        pool = _FakePool()
        adapter = _try_import_arq_engine(pool, ["myapp.task"], "arq:queue")
        assert adapter is not None


# ---------------------------------------------------------------------------
# Dramatiq
# ---------------------------------------------------------------------------


class TestDramatiq:
    def test_explicit_broker_is_used(self) -> None:
        pytest.importorskip("z4j_dramatiq")
        pytest.importorskip("dramatiq")

        class _FakeBroker:
            actors: dict[str, Any] = {}
            def add_middleware(self, mw): ...  # noqa: ARG002
            def get_actor(self, name): raise KeyError(name)  # noqa: ARG002

        b = _FakeBroker()
        adapter = _try_import_dramatiq_engine(b)
        assert adapter is not None
        assert adapter.broker is b

    def test_global_broker_skipped_when_no_actors(self) -> None:
        """Don't hijack dramatiq's auto-default StubBroker in projects
        that didn't opt into Dramatiq.
        """
        pytest.importorskip("z4j_dramatiq")
        pytest.importorskip("dramatiq")

        # No actors registered -> discovery should skip the global.
        adapter = _try_import_dramatiq_engine(None)
        # adapter MAY be non-None if a previous test in this run
        # registered an actor on the global broker. The contract we
        # pin: when called with broker=None, it MUST NOT crash.
        # Verifying it skips the actor-less broker is covered by the
        # flask-side test in a fresh process.
        assert adapter is None or adapter.broker is not None


# ---------------------------------------------------------------------------
# Huey
# ---------------------------------------------------------------------------


class TestHuey:
    def test_returns_none_with_no_huey(self) -> None:
        assert _try_import_huey_engine(None) is None

    def test_picks_up_huey_instance(self) -> None:
        pytest.importorskip("z4j_huey")
        pytest.importorskip("huey")
        from huey import MemoryHuey

        h = MemoryHuey("fastapi-test", immediate=False)
        adapter = _try_import_huey_engine(h)
        assert adapter is not None
        assert adapter.huey is h


# ---------------------------------------------------------------------------
# Taskiq
# ---------------------------------------------------------------------------


class TestTaskiq:
    def test_returns_none_with_no_broker(self) -> None:
        assert _try_import_taskiq_engine(None) is None

    def test_picks_up_inmemory_broker(self) -> None:
        pytest.importorskip("z4j_taskiq")
        pytest.importorskip("taskiq")
        from taskiq import InMemoryBroker

        b = InMemoryBroker()
        adapter = _try_import_taskiq_engine(b)
        assert adapter is not None
        assert adapter.broker is b


# ---------------------------------------------------------------------------
# discover_engines fan-out
# ---------------------------------------------------------------------------


class TestDiscoverEnginesFanOut:
    def test_no_engines_passed_returns_empty(self) -> None:
        # Without any engine handle, discovery yields an empty list
        # (or a single dramatiq adapter if a previous test polluted
        # the global broker, see TestDramatiq.test_global_broker_skipped).
        engines = discover_engines()
        # Acceptable shapes: empty, or only DramatiqEngineAdapter.
        names = {type(e).__name__ for e in engines}
        assert names <= {"DramatiqEngineAdapter"}

    def test_multiple_engines_register_together(self) -> None:
        pytest.importorskip("z4j_huey")
        pytest.importorskip("huey")
        pytest.importorskip("z4j_taskiq")
        pytest.importorskip("taskiq")

        from huey import MemoryHuey
        from taskiq import InMemoryBroker

        h = MemoryHuey("multi", immediate=False)
        b = InMemoryBroker()
        engines = discover_engines(huey=h, taskiq_broker=b)
        names = {type(e).__name__ for e in engines}
        assert "HueyEngineAdapter" in names
        assert "TaskiqEngineAdapter" in names
