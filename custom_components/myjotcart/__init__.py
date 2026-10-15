"""MyJotCart: shared shopping lists and home pantry, as Home Assistant to-do lists."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MyJotCartApi
from .const import CONF_TOKEN, CONF_URL
from .coordinator import MyJotCartCoordinator

PLATFORMS = [Platform.TODO, Platform.SENSOR]

type MyJotCartConfigEntry = ConfigEntry[MyJotCartCoordinator]


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
