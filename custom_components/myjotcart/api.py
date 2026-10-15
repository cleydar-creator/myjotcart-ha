"""Small client for the MyJotCart server (the add-on or a standalone install)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class MyJotCartError(Exception):
    """MyJotCart did not answer."""


class MyJotCartAuthError(MyJotCartError):
    """The token was rejected."""


class MyJotCartApi:
    """Talks to the MyJotCart REST API with a Home Assistant token (hat_…)."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _req(self, method: str, path: str, json: Any = None) -> Any:
        try:
            async with self._session.request(
                method, self.url + path, json=json, headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    raise MyJotCartAuthError
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise MyJotCartError((data or {}).get("error") or f"HTTP {resp.status}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise MyJotCartError(str(err) or type(err).__name__) from err

    async def state(self) -> dict[str, Any]:
        return await self._req("GET", "/api/state")

    async def add_item(self, list_id: str, name: str, qty: int = 1, note: str = "") -> dict:
        return await self._req("POST", "/api/items", {"listId": list_id, "name": name, "qty": qty, "note": note})

    async def update_item(self, item_id: str, **fields: Any) -> dict:
        return await self._req("PATCH", f"/api/items/{item_id}", fields)

    async def delete_item(self, item_id: str) -> None:
        await self._req("DELETE", f"/api/items/{item_id}")

    async def finish(self, list_id: str) -> dict:
        """Finish the shopping: ticked items leave the list and go into the home stock."""
        return await self._req("POST", f"/api/lists/{list_id}/finish")

    async def listen(self, on_change: Callable[[int], Awaitable[None]]) -> None:
        """Follow /api/live (Server-Sent Events) and call on_change(version). Returns when the stream ends."""
        async with self._session.get(
            self.url + "/api/live", headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=None, sock_read=90),
        ) as resp:
            if resp.status == 401:
                raise MyJotCartAuthError
            resp.raise_for_status()
            async for raw in resp.content:
                line = raw.decode(errors="ignore").strip()
                if line.startswith("data:"):
                    try:
                        await on_change(int(line[5:].strip()))
                    except ValueError:
                        continue
