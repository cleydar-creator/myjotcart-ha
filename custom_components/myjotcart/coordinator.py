"""Keeps the MyJotCart state; refreshed instantly through the live stream, polled as a fallback."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyJotCartApi, MyJotCartAuthError, MyJotCartError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyJotCartCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Whole household state (lists, items, products) — it is small."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: MyJotCartApi) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5),
            # a change in the app shows up in HA within ~1 s (the default waits up to 10 s between refreshes)
            request_refresh_debouncer=Debouncer(hass, _LOGGER, cooldown=1, immediate=True),
        )
        self.api = api
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.state()
        except MyJotCartAuthError as err:
            raise ConfigEntryAuthFailed from err
        except MyJotCartError as err:
            raise UpdateFailed(str(err)) from err

    async def _on_change(self, version: int) -> None:
        if not self.data or version != self.data.get("version"):
            await self.async_request_refresh()

    async def listen_forever(self) -> None:
        """Background task: reconnects to the live stream with a growing pause."""
        delay = 5
        while True:
            try:
                await self.api.listen(self._on_change)
                delay = 5
            except asyncio.CancelledError:
                raise
            except MyJotCartAuthError:
                _LOGGER.warning("MyJotCart rejected the token on the live stream")
                delay = 300
            except Exception as err:  # noqa: BLE001 — any network hiccup: try again later
                _LOGGER.debug("MyJotCart live stream closed: %s", err)
                delay = min(delay * 2, 120)
            await asyncio.sleep(delay)

    # Helpers used by the entities
    def lists(self) -> list[dict]:
        return sorted((self.data or {}).get("lists", []), key=lambda l: l.get("order", 0))

    def items(self, list_id: str) -> list[dict]:
        return [i for i in (self.data or {}).get("items", []) if i.get("listId") == list_id]

    def low_products(self) -> list[dict]:
        """Same rule as the app: nothing left at home, or under the minimum."""
        out = []
        for p in (self.data or {}).get("products", []):
            if p.get("hidden"):
                continue
            stock, mn = p.get("stock") or 0, p.get("min") or 0
            if stock <= 0 or (mn > 0 and stock < mn):
                out.append(p)
        return out
