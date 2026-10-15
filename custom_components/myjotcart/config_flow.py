"""Set up MyJotCart: found automatically when it runs as an add-on, or by hand with an address and a token."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import MyJotCartApi, MyJotCartAuthError, MyJotCartError
from .const import CONF_TOKEN, CONF_URL, DOMAIN


class MyJotCartConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}

    async def _check(self, url: str, token: str) -> tuple[str | None, dict]:
        """Returns (error key, state)."""
        try:
            state = await MyJotCartApi(async_get_clientsession(self.hass), url, token).state()
        except MyJotCartAuthError:
            return "invalid_auth", {}
        except MyJotCartError:
            return "cannot_connect", {}
        return None, state

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                url = "http://" + url
            err, state = await self._check(url, user_input[CONF_TOKEN].strip())
            if err:
                errors["base"] = err
            else:
                await self.async_set_unique_id(state["hid"])
                self._abort_if_unique_id_configured(updates={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN].strip()})
                return self.async_create_entry(title="MyJotCart", data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN].strip()})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=(user_input or {}).get(CONF_URL, "http://homeassistant.local:8210")): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """The MyJotCart add-on announced itself through the Supervisor."""
        cfg = discovery_info.config
        url, token = f"http://{cfg['host']}:{cfg['port']}", cfg["token"]
        err, state = await self._check(url, token)
        if err:
            return self.async_abort(reason=err)
        await self.async_set_unique_id(state["hid"])
        self._abort_if_unique_id_configured(updates={CONF_URL: url, CONF_TOKEN: token})
        self._discovered = {CONF_URL: url, CONF_TOKEN: token}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="MyJotCart", data=self._discovered)
        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            err, _ = await self._check(entry.data[CONF_URL], user_input[CONF_TOKEN].strip())
            if not err:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN].strip()})
            errors["base"] = err
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}), errors=errors)
