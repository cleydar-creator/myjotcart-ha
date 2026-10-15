"""The dashboard card: JS is served and the card can ask where the app is."""

from homeassistant.core import HomeAssistant

from .test_live import URL, pytestmark, setup  # noqa: F401


async def test_card(hass: HomeAssistant, hass_ws_client, hass_client):
    await setup(hass)
    client = await hass_client()
    r = await client.get("/myjotcart/myjotcart-card.js")
    assert r.status == 200 and "myjotcart-card" in await r.text()
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "myjotcart/app"})
    res = await ws.receive_json()
    assert res["success"] and res["result"] == {"slug": None, "url": URL}, res


async def test_card_addon_slug(hass: HomeAssistant, hass_ws_client):
    """Set up through the add-on discovery → the address is the add-on hostname → slug for ingress."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from unittest.mock import patch
    entry = MockConfigEntry(domain="myjotcart", unique_id="x", data={"url": "http://a0d7b954-myjotcart:8210", "token": "hat_x"})
    entry.add_to_hass(hass)
    with patch("custom_components.myjotcart.MyJotCartCoordinator._async_update_data", return_value={"lists": [], "items": [], "products": []}), \
         patch("custom_components.myjotcart.MyJotCartCoordinator.listen_forever", return_value=None):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ws = await hass_ws_client(hass)
        await ws.send_json({"id": 1, "type": "myjotcart/app"})
        res = await ws.receive_json()
        assert res["result"]["slug"] == "a0d7b954_myjotcart", res
        assert await hass.config_entries.async_unload(entry.entry_id)
