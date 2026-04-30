"""Tests for the FastAPI declarative reconciler (1.2.2+).

Covers:

- :func:`reconcile_schedules` standalone API
- ``reconcile_autorun=True`` kwarg on :func:`z4j_lifespan`
- Best-effort behaviour when the brain is unreachable
"""

from __future__ import annotations

import json

import httpx
import pytest

from z4j_bare.declarative import ScheduleReconciler
from z4j_fastapi.declarative import reconcile_schedules


def _make_handler(captured: dict) -> "callable":
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "inserted": 1,
                "updated": 0,
                "unchanged": 0,
                "failed": 0,
                "deleted": 0,
                "errors": {},
            },
        )

    return handler


def _patch_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    def patched(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.brain_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(ScheduleReconciler, "_http_client", patched)


# ---------------------------------------------------------------------------
# Standalone reconcile_schedules
# ---------------------------------------------------------------------------


class TestReconcileSchedules:
    def test_no_schedules_returns_none(self) -> None:
        result = reconcile_schedules(
            brain_url="http://b", api_key="k", project_slug="proj",
        )
        assert result is None

    def test_native_schedules_post_to_import(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict = {}
        _patch_http(monkeypatch, _make_handler(captured))

        result = reconcile_schedules(
            brain_url="http://b",
            api_key="my-key",
            project_slug="myproj",
            z4j_schedules={
                "x": {
                    "task": "myapp.tasks.x",
                    "kind": "cron",
                    "expression": "0 9 * * *",
                },
            },
        )
        assert result is not None
        assert result.inserted == 1
        assert "/projects/myproj/schedules:import" in captured["url"]
        assert captured["auth"] == "Bearer my-key"
        assert captured["body"]["mode"] == "replace_for_source"
        assert captured["body"]["source_filter"] == "declarative:fastapi"

    def test_celery_beat_schedules(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict = {}
        _patch_http(monkeypatch, _make_handler(captured))

        result = reconcile_schedules(
            brain_url="http://b",
            api_key="k",
            project_slug="proj",
            celery_beat_schedules={
                "every-min": {"task": "myapp.tasks.tick", "schedule": 60},
            },
        )
        assert result is not None
        assert len(captured["body"]["schedules"]) == 1
        assert captured["body"]["schedules"][0]["expression"] == "60"

    def test_dry_run_calls_diff(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(
                200,
                json={"insert": 2, "update": 1, "unchanged": 5, "delete": 0},
            )

        _patch_http(monkeypatch, handler)

        result = reconcile_schedules(
            brain_url="http://b",
            api_key="k",
            project_slug="proj",
            z4j_schedules={
                "x": {
                    "task": "myapp.tasks.x",
                    "kind": "interval",
                    "expression": "60",
                },
            },
            dry_run=True,
        )
        assert result is not None
        assert result.dry_run is True
        assert result.inserted == 2
        assert "/schedules:diff" in captured["url"]

    def test_custom_source_tag_used(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict = {}
        _patch_http(monkeypatch, _make_handler(captured))

        reconcile_schedules(
            brain_url="http://b",
            api_key="k",
            project_slug="proj",
            z4j_schedules={
                "x": {"task": "t", "kind": "cron", "expression": "0 9 * * *"},
            },
            source="my-deploy-script",
        )
        assert captured["body"]["source_filter"] == "my-deploy-script"
        assert captured["body"]["schedules"][0]["source"] == "my-deploy-script"

    def test_scheduler_owner_override(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict = {}
        _patch_http(monkeypatch, _make_handler(captured))

        reconcile_schedules(
            brain_url="http://b",
            api_key="k",
            project_slug="proj",
            z4j_schedules={
                "x": {"task": "t", "kind": "cron", "expression": "0 9 * * *"},
            },
            scheduler="z4j-scheduler-staging",
        )
        assert captured["body"]["schedules"][0]["scheduler"] == (
            "z4j-scheduler-staging"
        )


# ---------------------------------------------------------------------------
# z4j_lifespan reconcile_autorun
# ---------------------------------------------------------------------------


class TestLifespanAutorun:
    @pytest.mark.asyncio
    async def test_autorun_calls_reconcile(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Disable the agent runtime entirely so we only exercise
        # the reconcile path.
        monkeypatch.setenv("Z4J_DISABLED", "1")

        captured: dict = {}
        _patch_http(monkeypatch, _make_handler(captured))

        from z4j_fastapi import z4j_lifespan

        lifespan = z4j_lifespan(
            brain_url="http://b",
            token="my-key",
            project_id="myproj",
            reconcile_autorun=True,
            z4j_schedules={
                "x": {
                    "task": "myapp.tasks.x",
                    "kind": "cron",
                    "expression": "0 9 * * *",
                },
            },
        )

        async with lifespan(app=None):
            pass

        assert "url" in captured
        assert "/projects/myproj/schedules:import" in captured["url"]

    @pytest.mark.asyncio
    async def test_autorun_off_by_default(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without reconcile_autorun, no HTTP call is made."""
        monkeypatch.setenv("Z4J_DISABLED", "1")

        captured: dict = {}
        _patch_http(monkeypatch, _make_handler(captured))

        from z4j_fastapi import z4j_lifespan

        lifespan = z4j_lifespan(
            brain_url="http://b",
            token="k",
            project_id="proj",
            z4j_schedules={
                "x": {
                    "task": "myapp.tasks.x",
                    "kind": "cron",
                    "expression": "0 9 * * *",
                },
            },
        )

        async with lifespan(app=None):
            pass

        # No HTTP call, reconcile_autorun defaulted to False.
        assert "url" not in captured

    @pytest.mark.asyncio
    async def test_autorun_failure_does_not_crash_app(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If reconcile blows up, lifespan still completes."""
        monkeypatch.setenv("Z4J_DISABLED", "1")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        _patch_http(monkeypatch, handler)

        from z4j_fastapi import z4j_lifespan

        lifespan = z4j_lifespan(
            brain_url="http://b",
            token="k",
            project_id="proj",
            reconcile_autorun=True,
            z4j_schedules={
                "x": {
                    "task": "myapp.tasks.x",
                    "kind": "cron",
                    "expression": "0 9 * * *",
                },
            },
        )

        # Must not raise.
        async with lifespan(app=None):
            pass

    @pytest.mark.asyncio
    async def test_autorun_skips_when_brain_url_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("Z4J_DISABLED", "1")

        from z4j_fastapi import z4j_lifespan

        lifespan = z4j_lifespan(
            # brain_url omitted - reconcile should be skipped
            token="k",
            project_id="proj",
            reconcile_autorun=True,
            z4j_schedules={
                "x": {
                    "task": "myapp.tasks.x",
                    "kind": "cron",
                    "expression": "0 9 * * *",
                },
            },
        )

        async with lifespan(app=None):
            pass

        # Skipping was logged.
        assert any(
            "missing" in r.message.lower() for r in caplog.records
        )
