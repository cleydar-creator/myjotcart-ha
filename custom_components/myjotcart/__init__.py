"""MyJotCart: shared shopping lists and home pantry, as Home Assistant to-do lists."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import MyJotCartApi
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .coordinator import MyJotCartCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_URL = "/myjotcart/myjotcart-card.js"

PLATFORMS = [Platform.TODO, Platform.SENSOR]

type MyJotCartConfigEntry = ConfigEntry[MyJotCartCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The «MyJotCart» dashboard card: the whole app inside a dashboard, also from outside home (through ingress)."""
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / "myjotcart-card.js"), False)]
    )
    frontend.add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    websocket_api.async_register_command(hass, ws_app)
    return True


@websocket_api.websocket_command({vol.Required("type"): "myjotcart/app"})
@callback
def ws_app(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Where the card finds the app: the add-on slug (→ ingress, works remotely) and the direct address."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_found", "MyJotCart is not set up")
        return
    url = entries[0].data[CONF_URL]
    host = urlparse(url).hostname or ""
    # The add-on's hostname inside Home Assistant is its slug with «_» → «-» (e.g. a0d7b954-myjotcart).
    slug = host.replace("-", "_") if host.endswith("myjotcart") and "." not in host else None
    connection.send_result(msg["id"], {"slug": slug, "url": url})


async def async_setup_entry(hass: HomeAssistant, entry: MyJotCartConfigEntry) -> bool:
    api = MyJotCartApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = MyJotCartCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, coordinator.listen_forever(), "myjotcart_live")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyJotCartConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
