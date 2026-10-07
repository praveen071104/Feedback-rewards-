"""Shared types + BaseAI (cache + budget + stats + batching).

Ported verbatim from the StyleGraph reference (`copilot_ai.py`), adapted only for
project naming. Keep behaviour identical so the Copilot SDK path can be swapped
in with no caller changes.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class AITool:
    name: str
    description: str
    parameters: dict
    fn: Callable[[dict], dict]


@dataclass
class AIRequest:
    task: str
    system: str
    payload: dict
    schema: dict
    tools: list[AITool] = field(default_factory=list)


@dataclass
class AIStats:
    calls: int = 0
    cache_hits: int = 0
    budget_skips: int = 0
    errors: int = 0
    tool_calls: int = 0
    seconds: float = 0.0
    by_task: dict = field(default_factory=dict)
    last_error: str = ""

    def as_dict(self) -> dict:
        base = {k: getattr(self, k) for k in
                ("calls", "cache_hits", "budget_skips", "errors", "tool_calls", "by_task", "last_error")}
        return base | {"seconds": round(self.seconds, 1)}


class BaseAI:
    """Shared caching/budget logic. Subclasses implement `_run_many`."""

    def __init__(self, model: str, max_calls: int = 60, concurrency: int = 4, timeout: float = 120.0,
                 cache_path: Path | None = None, prompt_version: str = "1",
                 task_caps: dict[str, int] | None = None):
        self.model = model
        self.max_calls = max_calls
        self.task_caps = dict(task_caps or {})
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.cache_path = Path(cache_path) if cache_path else None
        self.prompt_version = prompt_version
        self.stats = AIStats()
        self._cache = self._load_cache()
        self._lock = threading.Lock()

    @property
    def label(self) -> str:
        return f"copilot:{self.model}"

    def _load_cache(self) -> dict:
        if self.cache_path and self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")

    def _key(self, r: AIRequest) -> str:
        blob = json.dumps([self.model, self.prompt_version, r.task, r.system, r.payload, r.schema,
                           [t.name for t in r.tools]], sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def ask(self, req: AIRequest) -> dict | None:
        return self.ask_many([req])[0]

    def ask_many(self, reqs: list[AIRequest]) -> list[dict | None]:
        out: list[dict | None] = [None] * len(reqs)
        todo: list[int] = []
        pending: dict[str, int] = {}
        for i, r in enumerate(reqs):
            hit = self._cache.get(self._key(r))
            used = self.stats.by_task.get(r.task, 0) + pending.get(r.task, 0)
            if hit is not None:
                self.stats.cache_hits += 1
                out[i] = hit
            elif (self.stats.calls + len(todo) < self.max_calls
                  and used < self.task_caps.get(r.task, self.max_calls)):
                todo.append(i)
                pending[r.task] = pending.get(r.task, 0) + 1
            else:
                self.stats.budget_skips += 1
        if todo:
            t0 = time.perf_counter()
            self.stats.calls += len(todo)
            for i in todo:
                self.stats.by_task[reqs[i].task] = self.stats.by_task.get(reqs[i].task, 0) + 1
            answers = self._run_many([reqs[i] for i in todo])
            self.stats.seconds += time.perf_counter() - t0
            for i, ans in zip(todo, answers):
                if isinstance(ans, Exception) or ans is None:
                    self.stats.errors += 1
                    self.stats.last_error = f"{type(ans).__name__}: {ans}"[:300]
                    continue
                out[i] = ans
                self._cache[self._key(reqs[i])] = ans
            self._save_cache()
        return out

    def _run_many(self, reqs: list[AIRequest]) -> list[dict | Exception]:
        raise NotImplementedError

    def _call_tool(self, tool: AITool, args: dict) -> str:
        with self._lock:
            self.stats.tool_calls += 1
        try:
            return json.dumps(tool.fn(args or {}))
        except Exception as exc:  # the model sees the error and can recover
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})

    def close(self) -> None:
        pass
