"""Factory that returns a `BaseAI` instance from a policy dict.

Signature matches the StyleGraph reference (`ai_from_policy(policy, cache_path)`).
`policy` is loaded from `policy.json` at app start. The `LLM_BACKEND` env var
selects the backend: `scripted` (VADER+rules), `trained` (synthetic ABSA model),
or `copilot` (real SDK).
"""
from __future__ import annotations

import os
from pathlib import Path

from app.config import settings
from app.llm.base import BaseAI
from app.llm.scripted_triage import scripted_responder


def ai_from_policy(policy: dict, cache_path: Path | None = None) -> BaseAI:
    cfg = policy.get("ai", {})
    model = os.environ.get("FEEDBACK_COPILOT_MODEL") or cfg.get("model", "claude-3.5-sonnet")
    max_calls = int(os.environ.get("FEEDBACK_AI_MAX_CALLS") or cfg.get("max_calls_per_run", 60))
    kwargs = dict(
        model=model,
        max_calls=max_calls,
        concurrency=cfg.get("concurrency", 4),
        timeout=cfg.get("timeout_seconds", 120),
        prompt_version=str(cfg.get("prompt_version", "1")),
        task_caps=cfg.get("task_max_calls"),
    )
    backend = (settings.llm_backend or "scripted").lower()
    if backend == "copilot":
        from app.llm.copilot_ai import CopilotAI
        return CopilotAI(cache_path=cache_path, **kwargs)
    if backend == "trained":
        from app.llm.scripted_ai import ScriptedAI
        from app.llm.trained_absa import ensure_loaded, trained_responder
        ensure_loaded()
        return ScriptedAI(responder=trained_responder, cache_path=None, **{**kwargs, "model": "absa-trained-v1"})
    from app.llm.scripted_ai import ScriptedAI
    return ScriptedAI(responder=scripted_responder, cache_path=None, **kwargs)
