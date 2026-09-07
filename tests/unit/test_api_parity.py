"""Sync/Async JSONPlaceholder domain API parity contract"""

import inspect
from collections.abc import Callable
from typing import Any

import pytest

from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient
from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient

pytestmark = pytest.mark.unit


INTENTIONALLY_ASYNC_ONLY: dict[str, str] = {
    # Intentional async-only: this method demonstrates concurrent fan-out.
    "bulk_create_users": "Uses a rolling admission window to bound in-flight user creation tasks.",
    # Intentional async-only: bounded concurrency is the behavior under demonstration.
    "get_multiple_users": "Uses a rolling admission window to bound in-flight user requests.",
    # Intentional async-only: TaskGroup cancellation behavior is being demonstrated.
    "get_user_data": "Uses asyncio.TaskGroup for concurrent related-data requests.",
}


def _public_methods(client_class: type[Any]) -> dict[str, Callable[..., Any]]:
    """Return public methods defined directly on a client class."""
    methods: dict[str, Callable[..., Any]] = {}
    for name, raw_member in vars(client_class).items():
        if name.startswith("_"):
            continue

        member: Any = raw_member
        if isinstance(member, (staticmethod, classmethod)):
            member = member.__func__
        if inspect.isfunction(member):
            methods[name] = member
    return methods


def test_sync_async_domain_method_parity() -> None:
    sync_methods = _public_methods(SyncJSONPlaceholderClient)
    async_methods = _public_methods(AsyncJSONPlaceholderClient)
    sync_names = set(sync_methods)
    async_names = set(async_methods)
    expected_async_only = set(INTENTIONALLY_ASYNC_ONLY)

    assert all(reason.strip() for reason in INTENTIONALLY_ASYNC_ONLY.values()), (
        "Every intentional async-only method must have a non-empty reason."
    )
    assert sync_names - async_names == set(), (
        "Sync-only public methods are not allowed. Add the method to both domain classes. "
        f"Found: {sorted(sync_names - async_names)}"
    )
    assert async_names - sync_names == expected_async_only, (
        "Unexpected async-only public methods. Add the method to both domain classes or "
        "update the appropriate reasoned allowlist. "
        f"Found: {sorted(async_names - sync_names)}"
    )

    common_names = sync_names & async_names
    signature_mismatches = {
        name: (
            str(inspect.signature(sync_methods[name])),
            str(inspect.signature(async_methods[name])),
        )
        for name in common_names
        if inspect.signature(sync_methods[name]) != inspect.signature(async_methods[name])
    }
    assert signature_mismatches == {}, (
        "Common sync/async methods must have identical signatures (parameter names, "
        "annotations, defaults, and return type). Align both definitions before updating "
        f"an allowlist. Found: {signature_mismatches}"
    )

    coroutine_mismatches = {
        name
        for name in common_names
        if inspect.iscoroutinefunction(sync_methods[name])
        or not inspect.iscoroutinefunction(async_methods[name])
    }
    assert coroutine_mismatches == set(), (
        "Common methods must differ only by the async/await boundary. Keep the sync "
        "definition synchronous and the async definition coroutine-based. "
        f"Coroutine-shape mismatches: {sorted(coroutine_mismatches)}"
    )

    async_only_coroutine_mismatches = {
        name for name in expected_async_only if not inspect.iscoroutinefunction(async_methods[name])
    }
    assert async_only_coroutine_mismatches == set(), (
        "Allowlisted async-only methods must be coroutine-based. Convert the definition to "
        "'async def' or drop the entry from INTENTIONALLY_ASYNC_ONLY. "
        f"Found: {sorted(async_only_coroutine_mismatches)}"
    )
