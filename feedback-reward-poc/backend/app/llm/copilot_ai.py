"""Real GitHub Copilot SDK backend. Imports `copilot` lazily inside `_ensure_client`
so this module is importable even when the SDK is not installed."""
from __future__ import annotations

import asyncio
import json
import threading

from app.llm.base import AIRequest, AITool, BaseAI


class CopilotAI(BaseAI):
    """Uses the signed-in Copilot CLI user or `COPILOT_GITHUB_TOKEN`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="copilot-sdk", daemon=True)
        self._thread.start()
        self._client = None

    async def _ensure_client(self):
        if self._client is None:
            from copilot import CopilotClient  # lazy: optional dependency
            self._client = CopilotClient(log_level="error")
            await self._client.start()
        return self._client

    async def _one(self, req: AIRequest, sem: asyncio.Semaphore) -> dict:
        from copilot import Tool, ToolResult
        from copilot.session import PermissionHandler

        def wrap(t: AITool):
            def handler(inv):
                return ToolResult(text_result_for_llm=self._call_tool(t, inv.arguments), result_type="success")
            return Tool(name=t.name, description=t.description, parameters=t.parameters, handler=handler,
                        skip_permission=True)

        async with sem:
            client = await self._ensure_client()
            session = await client.create_session(
                model=self.model,
                on_permission_request=PermissionHandler.approve_all,
                tools=[wrap(t) for t in req.tools],
                available_tools=[t.name for t in req.tools],
                system_message={"mode": "replace", "content": req.system},
                infinite_sessions={"enabled": False},
                skip_custom_instructions=True, enable_skills=False, enable_session_store=False,
            )
            try:
                ev = await session.send_and_wait(
                    json.dumps(req.payload, separators=(",", ":")),
                    response_schema=req.schema, timeout=self.timeout,
                )
            finally:
                await session.disconnect()
        if ev is None or not getattr(ev.data, "content", None):
            raise RuntimeError("Copilot returned no answer")
        return json.loads(ev.data.content)

    async def _gather(self, reqs):
        sem = asyncio.Semaphore(self.concurrency)
        return await asyncio.gather(*(self._one(r, sem) for r in reqs), return_exceptions=True)

    def _run_many(self, reqs):
        fut = asyncio.run_coroutine_threadsafe(self._gather(reqs), self._loop)
        return fut.result(timeout=self.timeout * (len(reqs) // self.concurrency + 2))

    def close(self) -> None:
        if self._client is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._client.stop(), self._loop).result(timeout=30)
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
