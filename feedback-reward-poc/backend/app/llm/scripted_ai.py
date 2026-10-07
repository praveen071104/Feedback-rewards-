"""Offline stand-in used for tests, demos, and when the SDK is not installed."""
from __future__ import annotations

import json
from typing import Callable

from app.llm.base import AIRequest, BaseAI


class ScriptedAI(BaseAI):
    """`responder(task, payload, tools)` returns the answer dict."""

    def __init__(self, responder: Callable[[str, dict, dict], dict], **kwargs):
        kwargs.setdefault("cache_path", None)
        super().__init__(kwargs.pop("model", "scripted"), **kwargs)
        self.responder = responder
        self.requests: list[AIRequest] = []

    def _run_many(self, reqs):
        out = []
        for r in reqs:
            self.requests.append(r)
            tools = {t.name: (lambda args, t=t: json.loads(self._call_tool(t, args))) for t in r.tools}
            try:
                out.append(self.responder(r.task, r.payload, tools))
            except Exception as exc:
                out.append(exc)
        return out
