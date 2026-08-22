"""Shared test isolation for environment-backed external providers."""

from __future__ import annotations

import pytest

from backend.app.llm.providers.qwen import reset_qwen_provider


@pytest.fixture(autouse=True)
def _disable_real_qwen_for_unit_tests(monkeypatch: pytest.MonkeyPatch):
    """Unit tests must never depend on or call a developer's real DashScope account.

    Tests that exercise Qwen configure a fake client explicitly after this fixture.
    Online validation is run separately by the dedicated smoke test.
    """
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_MODEL", raising=False)
    reset_qwen_provider()
    yield
    reset_qwen_provider()
