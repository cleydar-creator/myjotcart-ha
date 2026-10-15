"""Voice: what Assist runs for «añade queso a la lista Alcampo» / «add bananas to my Alcampo list»
(the HassListAddItem intent, matched by list name). Needs a running MyJotCart, like test_live."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from .test_live import phone, pytestmark, setup  # noqa: F401


async def test_voice(hass: HomeAssistant):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    await setup(hass)
    for item, lst in (("queso", "Alcampo"), ("bananas", "alcampo")):
        r = await intent.async_handle(hass, "test", "HassListAddItem", {"item": {"value": item}, "name": {"value": lst}}, assistant="conversation")
        print(item, "→", r.response_type, r.speech)
    st = await phone("GET", "/api/state")
    alc = next(l["id"] for l in st["lists"] if l["name"] == "Alcampo")
    names = sorted(i["name"] for i in st["items"] if i["listId"] == alc)
    print("Alcampo:", names)
    assert names == ["bananas", "queso"]
